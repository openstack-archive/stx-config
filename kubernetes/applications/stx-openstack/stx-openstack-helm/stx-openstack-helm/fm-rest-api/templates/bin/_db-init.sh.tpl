#!/bin/bash

{{/*
#
# SPDX-License-Identifier: Apache-2.0
#
*/}}

set -ex

createdb -h 127.0.0.1 -Uroot -l C -T template0 -E utf8 fm
