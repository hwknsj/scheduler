__author__ = 'Bohdan Mushkevych'

from synergy.mx.base_request_handler import BaseRequestHandler, valid_action_request, safe_json_response
from synergy.db.dao.unit_of_work_dao import UnitOfWorkDao
from synergy.db.dao.log_recording_dao import LogRecordingDao


class AbstractActionHandler(BaseRequestHandler):
    def __init__(self, request, **values):
        super(AbstractActionHandler, self).__init__(request, **values)
        self.uow_dao = UnitOfWorkDao(self.logger)
        self.log_recording_dao = LogRecordingDao(self.logger)

    @property
    def thread_handler(self):
        raise NotImplementedError('property thread_handler must be implemented by {0}'.format(self.__class__.__name__))

    @property
    def process_entry(self):
        raise NotImplementedError('property process_entry must be implemented by {0}'.format(self.__class__.__name__))

    @property
    def uow_id(self):
        raise NotImplementedError('property uow_id must be implemented by {0}'.format(self.__class__.__name__))

    def get_event_log(self):
        raise NotImplementedError('method action_get_event_log must be implemented by {0}'
                                  .format(self.__class__.__name__))

    @safe_json_response
    def get_uow(self):
        if self.uow_id is None:
            resp = {'response': 'no related unit_of_work'}
        else:
            resp = self.uow_dao.get_one(self.uow_id).document
        return resp

    @safe_json_response
    def get_uow_log(self):
        try:
            resp = self.log_recording_dao.get_one(self.uow_id).document
        except (TypeError, LookupError):
            resp = {'response': 'no related uow log'}
        return resp

    @valid_action_request
    def change_interval(self):
        resp = dict()
        new_interval = self.request_arguments['interval']
        if new_interval is not None:
            self.thread_handler.change_interval(new_interval)
            msg = 'changed interval for {0} to {1}'.format(self.thread_handler.key, new_interval)
            self.logger.info('MX: {0}'.format(msg))
            resp['status'] = msg

        return resp

    @valid_action_request
    def trigger_now(self):
        self.thread_handler.trigger()
        self.logger.info('MX: triggered thread handler {0}'.format(self.thread_handler.key))
        return self.reply_ok()

    @valid_action_request
    def activate_trigger(self):
        self.thread_handler.activate()
        self.logger.info('MX: activated thread handler {0}'.format(self.thread_handler.key))
        return self.reply_ok()

    @valid_action_request
    def deactivate_trigger(self):
        self.thread_handler.deactivate()
        self.logger.info('MX: deactivated thread handler {0}'.format(self.thread_handler.key))
        return self.reply_ok()
