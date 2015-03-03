__author__ = 'Bohdan Mushkevych'

from datetime import datetime, timedelta
from threading import Lock

from amqp import AMQPError

from synergy.conf import context
from synergy.mq.flopsy import PublishersPool
from synergy.mx.synergy_mx import MX
from synergy.db.model.synergy_mq_transmission import SynergyMqTransmission
from synergy.db.model.managed_process_entry import ManagedProcessEntry
from synergy.db.model import managed_process_entry, job
from synergy.db.dao.scheduler_managed_entry_dao import SchedulerManagedEntryDao
from synergy.db.dao.scheduler_freerun_entry_dao import SchedulerFreerunEntryDao
from synergy.system import time_helper
from synergy.system.decorator import with_reconnect, thread_safe
from synergy.system.synergy_process import SynergyProcess
from synergy.scheduler.status_bus_listener import StatusBusListener
from synergy.scheduler.scheduler_constants import *
from synergy.scheduler.state_machine_continuous import StateMachineContinuous
from synergy.scheduler.state_machine_dicrete import StateMachineDiscrete
from synergy.scheduler.state_machine_simple_dicrete import StateMachineSimpleDiscrete
from synergy.scheduler.state_machine_freerun import StateMachineFreerun
from synergy.scheduler.timetable import Timetable
from synergy.scheduler.thread_handler import construct_thread_handler, ThreadHandlerArguments


class Scheduler(SynergyProcess):
    """ Scheduler hosts multiple state machines, and logic for triggering jobs """

    def __init__(self, process_name):
        super(Scheduler, self).__init__(process_name)
        self.lock = Lock()
        self.logger.info('Starting %s' % self.process_name)
        self.publishers = PublishersPool(self.logger)
        self.managed_handlers = dict()
        self.freerun_handlers = dict()
        self.timetable = Timetable(self.logger)
        self.state_machines = self._construct_state_machines()

        self.se_managed_dao = SchedulerManagedEntryDao(self.logger)
        self.se_freerun_dao = SchedulerFreerunEntryDao(self.logger)
        self.mx = None
        self.bus_listener = None
        self.logger.info('Started %s' % self.process_name)

    def __del__(self):
        for key, handler in self.managed_handlers.iteritems():
            handler.deactivate(update_persistent=False)
        self.managed_handlers.clear()

        for key, handler in self.freerun_handlers.iteritems():
            handler.deactivate(update_persistent=False)
        self.freerun_handlers.clear()

        self.publishers.close()

        super(Scheduler, self).__del__()

    def _construct_state_machines(self):
        """ :return: dict in format <state_machine_common_name: instance_of_the_state_machine> """
        state_machines = dict()
        for state_machine in [StateMachineContinuous(self.logger, self.timetable),
                              StateMachineDiscrete(self.logger, self.timetable),
                              StateMachineSimpleDiscrete(self.logger, self.timetable),
                              StateMachineFreerun(self.logger)]:
            state_machines[state_machine.name] = state_machine
        return state_machines

    def _register_scheduler_entry(self, scheduler_entry_obj, call_back):
        """ method parses scheduler_entry_obj and creates a timer_handler out of it
         timer_handler is enlisted to either :self.freerun_handlers or :self.managed_handlers
         timer_handler is started, unless it is marked as STATE_OFF """
        handler = construct_thread_handler(self.logger, scheduler_entry_obj, call_back)

        if handler.arguments.handler_type == TYPE_MANAGED:
            self.managed_handlers[handler.arguments.key] = handler
        elif handler.arguments.handler_type == TYPE_FREERUN:
            self.freerun_handlers[handler.arguments.key] = handler
        else:
            self.logger.error('Process/Handler type %s is not known to the system. Skipping it.'
                              % handler.arguments.handler_type)
            return

        if scheduler_entry_obj.state == managed_process_entry.STATE_ON:
            handler.activate()
            self.logger.info('Started scheduler thread for %s:%r.'
                             % (handler.arguments.handler_type, handler.arguments.key))
        else:
            self.logger.info('Handler for %s:%r registered in Scheduler. Idle until activated.'
                             % (handler.arguments.handler_type, handler.arguments.key))

    # **************** Scheduler Methods ************************
    def _load_managed_entries(self):
        """ loads scheduler managed entries. no start-up procedures are performed """
        scheduler_entries = self.se_managed_dao.get_all()
        for scheduler_entry_obj in scheduler_entries:
            process_name = scheduler_entry_obj.process_name
            if scheduler_entry_obj.process_name not in context.process_context:
                self.logger.error('Process %r is not known to the system. Skipping it.' % process_name)
                continue

            process_type = context.process_context[process_name].process_type
            if process_type == TYPE_MANAGED:
                function = self.fire_managed_worker
            elif process_type == TYPE_GARBAGE_COLLECTOR:
                function = self.fire_garbage_collector
            elif process_type in [TYPE_FREERUN, TYPE_DAEMON]:
                self.logger.error('%s processes are not managed by Synergy Scheduler. '
                                  'Remove the process %s from the scheduler_managed_entry table. Skipping the process.'
                                  % (process_type.upper(), process_name))
                continue
            else:
                self.logger.error('Process type %s is not known to the system. Skipping it.' % process_type)
                continue

            try:
                self._register_scheduler_entry(scheduler_entry_obj, function)
            except Exception:
                self.logger.error('Scheduler Handler %r failed to start. Skipping it.' % (scheduler_entry_obj.key,))

    def _load_freerun_entries(self):
        """ reads scheduler managed entries and starts their timers to trigger events """
        scheduler_entries = self.se_freerun_dao.get_all()
        for scheduler_entry_obj in scheduler_entries:
            try:
                self._register_scheduler_entry(scheduler_entry_obj, self.fire_freerun_worker)
            except Exception:
                self.logger.error('Scheduler Handler %r failed to start. Skipping it.' % (scheduler_entry_obj.key,))

    @with_reconnect
    def start(self, *_):
        """ reads scheduler entries and starts timer instances, as well as MX thread """
        try:
            self._load_managed_entries()
        except LookupError as e:
            self.logger.warn('DB Lookup: %s' % str(e))

        try:
            self._load_freerun_entries()
        except LookupError as e:
            self.logger.warn('DB Lookup: %s' % str(e))

        # Scheduler is initialized and running. Status Bus Listener can be safely started
        self.bus_listener = StatusBusListener(self)
        self.bus_listener.start()

        # All Scheduler components are initialized and running. Management Extension (MX) can be safely started
        self.mx = MX(self)
        self.mx.start_mx_thread()

    @thread_safe
    def fire_managed_worker(self, thread_handler_arguments):
        """requests next valid job for given process and manages its state"""

        def _fire_worker(process_name, scheduler_entry_obj):
            assert isinstance(scheduler_entry_obj, ManagedProcessEntry)
            job_record = self.timetable.get_next_job_record(process_name)
            state_machine = self.state_machines[scheduler_entry_obj.state_machine_name]

            run_on_active_timeperiod = context.process_context[process_name].run_on_active_timeperiod
            if not run_on_active_timeperiod:
                time_qualifier = context.process_context[process_name].time_qualifier
                incremented_timeperiod = time_helper.increment_timeperiod(time_qualifier, job_record.timeperiod)
                dt_record_timestamp = time_helper.synergy_to_datetime(time_qualifier, incremented_timeperiod)
                dt_record_timestamp += timedelta(minutes=LAG_5_MINUTES)

                if datetime.utcnow() <= dt_record_timestamp:
                    self.logger.info('Job record %s for timeperiod %s will not be triggered until %s.'
                                     % (job_record.db_id,
                                        job_record.timeperiod,
                                        dt_record_timestamp.strftime('%Y-%m-%d %H:%M:%S')))
                    return None

            blocking_type = scheduler_entry_obj.blocking_type
            if blocking_type == BLOCKING_DEPENDENCIES:
                state_machine.manage_job_with_blocking_dependencies(process_name, job_record, run_on_active_timeperiod)
            elif blocking_type == BLOCKING_CHILDREN:
                state_machine.manage_job_with_blocking_children(process_name, job_record, run_on_active_timeperiod)
            elif blocking_type == BLOCKING_NORMAL:
                state_machine.manage_job(process_name, job_record)
            else:
                raise ValueError('Unknown managed process type %s' % blocking_type)

            return job_record

        try:
            assert isinstance(thread_handler_arguments, ThreadHandlerArguments)
            self.logger.info('%r {' % (thread_handler_arguments.key, ))

            job_record = _fire_worker(thread_handler_arguments.key, thread_handler_arguments.scheduler_entry_obj)
            while job_record is not None and job_record.state in [job.STATE_SKIPPED, job.STATE_PROCESSED]:
                job_record = _fire_worker(thread_handler_arguments.key, thread_handler_arguments.scheduler_entry_obj)

        except (AMQPError, IOError) as e:
            self.logger.error('AMQPError: %s' % str(e), exc_info=True)
            self.publishers.reset_all(suppress_logging=True)
        except Exception as e:
            self.logger.error('Exception: %s' % str(e), exc_info=True)
        finally:
            self.logger.info('}')

    @thread_safe
    def fire_freerun_worker(self, thread_handler_arguments):
        """fires free-run worker with no dependencies to track"""
        try:
            assert isinstance(thread_handler_arguments, ThreadHandlerArguments)
            self.logger.info('%r {' % (thread_handler_arguments.key, ))

            state_machine = self.state_machines[STATE_MACHINE_FREERUN]
            state_machine.manage_schedulable(thread_handler_arguments.scheduler_entry_obj)

        except Exception as e:
            self.logger.error('fire_freerun_worker: %s' % str(e))
        finally:
            self.logger.info('}')

    @thread_safe
    def fire_garbage_collector(self, thread_handler_arguments):
        """fires garbage collector to re-trigger invalid unit_of_work"""
        try:
            assert isinstance(thread_handler_arguments, ThreadHandlerArguments)
            self.logger.info('%r {' % (thread_handler_arguments.key, ))
            mq_request = SynergyMqTransmission(process_name=thread_handler_arguments.key)

            publisher = self.publishers.get(thread_handler_arguments.key)
            publisher.publish(mq_request.document)
            publisher.release()
            self.logger.info('Published trigger for %s' % thread_handler_arguments.key)

            self.logger.info('Starting timetable housekeeping...')
            self.timetable.build_trees()
            self.timetable.validate()
            self.logger.info('Timetable housekeeping complete.')
        except (AMQPError, IOError) as e:
            self.logger.error('AMQPError: %s' % str(e), exc_info=True)
            self.publishers.reset_all(suppress_logging=True)
        except Exception as e:
            self.logger.error('fire_garbage_collector: %s' % str(e))
        finally:
            self.logger.info('}')


if __name__ == '__main__':
    from synergy.scheduler.scheduler_constants import PROCESS_SCHEDULER

    source = Scheduler(PROCESS_SCHEDULER)
    source.start()
