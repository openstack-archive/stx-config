# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sqlalchemy import Column, MetaData, Table
from sqlalchemy import DateTime, Integer, String
from sqlalchemy import ForeignKey, UniqueConstraint
from sysinv.openstack.common import log

ENGINE = 'InnoDB'
CHARSET = 'utf8'
LOG = log.getLogger(__name__)


def upgrade(migrate_engine):
    """Perform sysinv database upgrade for host label
    """

    meta = MetaData()
    meta.bind = migrate_engine

    Table('i_host', meta, autoload=True)

    label = Table(
        'label',
        meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('deleted_at', DateTime),

        Column('id', Integer, primary_key=True, nullable=False),
        Column('uuid', String(36), unique=True),

        Column('host_id', Integer, ForeignKey('i_host.id',
                                              ondelete='CASCADE')),

        Column('label_key', String(320)),
        Column('label_value', String(64)),
        UniqueConstraint('host_id', 'label_key', name='u_host_id@label_key'),

        mysql_engine=ENGINE,
        mysql_charset=CHARSET,
    )
    label.create()


def downgrade(migrate_engine):
    # As per other openstack components, downgrade is
    # unsupported in this release.
    raise NotImplementedError('SysInv database downgrade is unsupported.')
