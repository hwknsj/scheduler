__author__ = 'Bohdan Mushkevych'

from odm.document import BaseDocument
from odm.fields import StringField

MQ_QUEUE = 'mq_queue'
MQ_EXCHANGE = 'mq_exchange'
MQ_ROUTING_KEY = 'mq_routing_key'


class QueueContextEntry(BaseDocument):
    """ Non-persistent model. This class presents Queue Context Entry record """

    @BaseDocument.key.getter
    def key(self):
        return self.mq_queue

    @key.setter
    def key(self, value):
        """ :param value: name of the mq queue """
        self.mq_queue = value

    mq_queue = StringField(MQ_QUEUE)
    mq_exchange = StringField(MQ_EXCHANGE)
    mq_routing_key = StringField(MQ_ROUTING_KEY)


def _queue_context_entry(exchange,
                         queue_name,
                         routing=None):
    """ forms queue's context entry """
    if routing is None:
        routing = queue_name

    queue_entry = QueueContextEntry()
    queue_entry.mq_queue = queue_name
    queue_entry.mq_exchange = exchange
    queue_entry.mq_routing_key = routing
    return queue_entry
