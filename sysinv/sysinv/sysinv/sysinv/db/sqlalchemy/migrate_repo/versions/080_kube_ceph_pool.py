# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# The right to copy, distribute, modify, or otherwise make use
# of this software may be licensed only pursuant to the terms
# of an applicable Wind River license agreement.
#

from sqlalchemy import Integer
from sqlalchemy import Column, MetaData, Table

ENGINE = 'InnoDB'
CHARSET = 'utf8'


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    i_storconfig = Table('storage_ceph', meta, autoload=True)
    i_storconfig.create_column(Column('kube_pool_gib', Integer))


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    i_storconfig = Table('storage_ceph', meta, autoload=True)
    i_storconfig.drop_column('kube_pool_gib')
