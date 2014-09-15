__author__ = 'Bohdan Mushkevych'

from datetime import datetime, timedelta

from werkzeug.utils import cached_property

from db.model import scheduler_managed_entry
from scheduler.scheduler_constants import TYPE_FREERUN
from system.repeat_timer import RepeatTimer
from system.event_clock import EventClock, format_time_trigger_string
from system.process_context import ProcessContext
from system.performance_tracker import FootprintCalculator


# Scheduler Entries Details tab
class SchedulerEntries(object):
    def __init__(self, mbean):
        self.mbean = mbean
        self.logger = self.mbean.logger

    def _handler_last_active(self, thread_handler):
        return 'NA' if not thread_handler.is_alive() else thread_handler.activation_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

    def _handler_next_run(self, thread_handler):
        if not thread_handler.is_alive():
            return 'NA'

        next_run = thread_handler.next_run_in()
        return str(next_run).split('.')[0]

    def _handler_next_timeperiod(self, process_name):
        timetable = self.mbean.timetable
        if timetable.get_tree(process_name) is None:
            return 'NA'
        else:
            timetable_record = timetable.get_next_timetable_record(process_name)
            return timetable_record.timeperiod

    @cached_property
    def managed_entries(self):
        list_of_rows = []
        try:
            sorter_keys = sorted(self.mbean.managed_handlers.keys())
            for key in sorter_keys:
                thread_handler = self.mbean.managed_handlers[key]
                process_name = thread_handler.args[0]

                row = []
                # indicate whether process is in active or passive state
                # parameters are set in Scheduler.run() method
                row.append(thread_handler.args[1].process_state == scheduler_managed_entry.STATE_ON)    # index 0

                row.append(thread_handler.is_alive())                                           # index 1
                row.append(process_name)                                                        # index 2
                row.append(format_time_trigger_string(thread_handler))                          # index 3
                row.append(self._handler_next_run(thread_handler))                              # index 4
                row.append(self._handler_next_timeperiod(process_name))                         # index 5

                list_of_rows.append(row)
        except Exception as e:
            self.logger.error('MX Exception %s' % str(e), exc_info=True)

        return list_of_rows

    @cached_property
    def freerun_entries(self):
        list_of_rows = []
        try:
            sorter_keys = sorted(self.mbean.freerun_handlers.keys())
            for key in sorter_keys:
                thread_handler = self.mbean.freerun_handlers[key]
                process_name, entry_name = thread_handler.args[0]

                row = []
                # indicate whether process is in active or passive state
                # parameters are set in Scheduler.run() method
                row.append(thread_handler.args[1].process_state == scheduler_managed_entry.STATE_ON)    # index 0

                row.append(thread_handler.is_alive())                                           # index 1
                row.append(process_name)                                                        # index 2
                row.append(entry_name)                                                          # index 3
                row.append(format_time_trigger_string(thread_handler))                          # index 4
                row.append(self._handler_next_run(thread_handler))                              # index 5
                row.append(thread_handler.args[1].arguments)                                    # index 6

                list_of_rows.append(row)
        except Exception as e:
            self.logger.error('MX Exception %s' % str(e), exc_info=True)

        return list_of_rows

    @cached_property
    def footprint(self):
        try:
            calculator = FootprintCalculator()
            footprint = calculator.get_snapshot_as_list()
            return footprint
        except Exception as e:
            self.logger.error('MX Exception %s' % str(e), exc_info=True)