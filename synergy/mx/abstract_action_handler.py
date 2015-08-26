__author__ = 'Bohdan Mushkevych'

from synergy.mx.base_request_handler import BaseRequestHandler, valid_action_request


class AbstractActionHandler(BaseRequestHandler):
    def __init__(self, request, **values):
        super(AbstractActionHandler, self).__init__(request, **values)

    @property
    def thread_handler(self):
        raise NotImplementedError('property thread_handler must be implemented by {0}'.format(self.__class__.__name__))

    @property
    def process_entry(self):
        raise NotImplementedError('property process_entry must be implemented by {0}'.format(self.__class__.__name__))

    def action_get_uow(self):
        raise NotImplementedError('method action_get_uow must be implemented by {0}'.format(self.__class__.__name__))

    def action_get_log(self):
        raise NotImplementedError('method action_get_log must be implemented by {0}'.format(self.__class__.__name__))

    @valid_action_request
    def action_change_interval(self):
        resp = dict()
        new_interval = self.request_arguments['interval']
        if new_interval is not None:
            thread_handler = self.thread_handler
            thread_handler.change_interval(new_interval)
            resp['status'] = 'changed interval for %r to %r' % (thread_handler.key, new_interval)

        return resp

    @valid_action_request
    def action_trigger_now(self):
        self.thread_handler.trigger()
        return self.reply_ok()

    @valid_action_request
    def action_activate_trigger(self):
        self.thread_handler.activate()
        return self.reply_ok()

    @valid_action_request
    def action_deactivate_trigger(self):
        self.thread_handler.deactivate()
        return self.reply_ok()
