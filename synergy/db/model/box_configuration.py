__author__ = 'Bohdan Mushkevych'

from odm.document import BaseDocument
from odm.fields import StringField, ObjectIdField, IntegerField, BooleanField

BOX_ID = 'box_id'
PROCESS_NAME = 'process_name'
PID = 'pid'
IS_ON = 'is_on'


class BoxConfiguration(BaseDocument):
    """
    Class presents list of processes that are supposed to run on particular box.
    """
    db_id = ObjectIdField('_id', null=True)
    box_id = StringField(BOX_ID)
    process_name = StringField(PROCESS_NAME)
    is_on = BooleanField(IS_ON, default=False)
    pid = IntegerField(PID, null=True)
