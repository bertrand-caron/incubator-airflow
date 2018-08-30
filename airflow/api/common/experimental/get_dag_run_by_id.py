# -*- coding: utf-8 -*-
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from flask import url_for

from airflow.exceptions import DagNotFound, DagRunNotFound
from airflow.models import DagBag, DagRun
from airflow import configuration as conf

is_rbac = conf.getboolean('webserver', 'rbac')


def get_dag_run_by_id(dag_id, run_id):
    """
    Returns a Dag Run for a specific DAG ID/Run ID.
    :param dag_id: String identifier of a DAG
    :param run_id: Dag run id
    :return: DAG run of the requested run_id
    """
    dagbag = DagBag()

    # Check DAG exists.
    if dag_id not in dagbag.dags:
        error_message = "Dag id {} not found".format(dag_id)
        raise DagNotFound(error_message)

    run = DagRun.find(dag_id=dag_id, run_id=run_id)
    if run is None or len(run) == 0:
        error_message = "Dag id {} run_id {} not found".format(dag_id, run_id)
        raise DagRunNotFound(error_message)

    return {
        'id': run[0].id,
        'run_id': run[0].run_id,
        'state': run[0].state,
        'dag_id': run[0].dag_id,
        'execution_date': run[0].execution_date.isoformat(),
        'start_date': ((run[0].start_date or '') and
                       run[0].start_date.isoformat()),
        'dag_run_url': url_for('Airflow.graph' if is_rbac else 'airflow.graph', dag_id=run[0].dag_id,
                               execution_date=run[0].execution_date)
    }
