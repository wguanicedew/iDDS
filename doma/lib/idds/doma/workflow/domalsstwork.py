#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2020 - 2021
# - Sergey Padolski, <spadolski@bnl.gov>, 2020


try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

import copy
import datetime
import os
import traceback
import uuid

from idds.common import exceptions
from idds.common.constants import (TransformType, CollectionStatus, CollectionType,
                                   ContentStatus, ContentType,
                                   ProcessingStatus, WorkStatus)
from idds.workflow.work import Work
from idds.workflow.workflow import Condition


class DomaCondition(Condition):
    def __init__(self, cond=None, current_work=None, true_work=None, false_work=None):
        super(DomaCondition, self).__init__(cond=cond, current_work=current_work,
                                            true_work=true_work, false_work=false_work)


class DomaLSSTWork(Work):
    def __init__(self, executable=None, arguments=None, parameters=None, setup=None,
                 work_tag='lsst', exec_type='panda', sandbox=None, work_id=None,
                 primary_input_collection=None, other_input_collections=None,
                 output_collections=None, log_collections=None,
                 logger=None, dependency_map=None, task_name="", task_queue=None, processing_type=None,
                 prodSourceLabel='test', task_type='test', maxwalltime=90000, maxattempt=5, core_count=1):

        super(DomaLSSTWork, self).__init__(executable=executable, arguments=arguments,
                                           parameters=parameters, setup=setup, work_type=TransformType.Processing,
                                           work_tag=work_tag, exec_type=exec_type, sandbox=sandbox, work_id=work_id,
                                           primary_input_collection=primary_input_collection,
                                           other_input_collections=other_input_collections,
                                           output_collections=output_collections,
                                           log_collections=log_collections,
                                           release_inputs_after_submitting=True,
                                           logger=logger)
        # self.pandamonitor = None
        self.panda_url = None
        self.panda_url_ssl = None
        self.panda_monitor = None

        self.dependency_map = dependency_map
        self.dependency_map_deleted = []
        # self.logger.setLevel(logging.DEBUG)

        self.task_name = task_name
        self.set_work_name(task_name)
        self.queue = task_queue
        self.dep_tasks_id_names_map = {}
        self.executable = executable
        self.processingType = processing_type
        self.prodSourceLabel = prodSourceLabel
        self.task_type = task_type
        self.maxWalltime = maxwalltime
        self.maxAttempt = maxattempt
        self.core_count = core_count

        self.load_panda_urls()

        self.pandamonitor = None
        self.jobs_cache = {}

    def my_condition(self):
        if self.is_finished():
            return True
        return False

    def copy(self):
        self.set_work_name(self.task_name)
        new_work = copy.deepcopy(self)
        return new_work

    def load_panda_config(self):
        panda_config = ConfigParser.SafeConfigParser()
        if os.environ.get('IDDS_PANDA_CONFIG', None):
            configfile = os.environ['IDDS_PANDA_CONFIG']
            if panda_config.read(configfile) == [configfile]:
                return panda_config

        configfiles = ['%s/etc/panda/panda.cfg' % os.environ.get('IDDS_HOME', ''),
                       '/etc/panda/panda.cfg', '/opt/idds/etc/panda/panda.cfg',
                       '%s/etc/panda/panda.cfg' % os.environ.get('VIRTUAL_ENV', '')]
        for configfile in configfiles:
            if panda_config.read(configfile) == [configfile]:
                return panda_config
        return panda_config

    def load_panda_urls(self):
        panda_config = self.load_panda_config()
        self.logger.debug("panda config: %s" % panda_config)
        self.panda_url = None
        self.panda_url_ssl = None
        self.panda_monitor = None

        if panda_config.has_section('panda'):
            if panda_config.has_option('panda', 'panda_monitor_url'):
                self.panda_monitor = panda_config.get('panda', 'panda_monitor_url')
                os.environ['PANDA_MONITOR_URL'] = self.panda_monitor
                self.logger.debug("Panda monitor url: %s" % str(self.panda_monitor))
            if panda_config.has_option('panda', 'panda_url'):
                self.panda_url = panda_config.get('panda', 'panda_url')
                os.environ['PANDA_URL'] = self.panda_url
                self.logger.debug("Panda url: %s" % str(self.panda_url))
            if panda_config.has_option('panda', 'panda_url_ssl'):
                self.panda_url_ssl = panda_config.get('panda', 'panda_url_ssl')
                os.environ['PANDA_URL_SSL'] = self.panda_url_ssl
                self.logger.debug("Panda url ssl: %s" % str(self.panda_url_ssl))

        if not self.panda_monitor and 'PANDA_MONITOR_URL' in os.environ and os.environ['PANDA_MONITOR_URL']:
            self.panda_monitor = os.environ['PANDA_MONITOR_URL']
            self.logger.debug("Panda monitor url: %s" % str(self.panda_monitor))
        if not self.panda_url and 'PANDA_URL' in os.environ and os.environ['PANDA_URL']:
            self.panda_url = os.environ['PANDA_URL']
            self.logger.debug("Panda url: %s" % str(self.panda_url))
        if not self.panda_url_ssl and 'PANDA_URL_SSL' in os.environ and os.environ['PANDA_URL_SSL']:
            self.panda_url_ssl = os.environ['PANDA_URL_SSL']
            self.logger.debug("Panda url ssl: %s" % str(self.panda_url_ssl))

    def clean_work(self):
        self.dependency_map_deleted = []
        self.dependency_map = []

    def poll_external_collection(self, coll):
        try:
            if 'status' in coll and coll['status'] in [CollectionStatus.Closed]:
                return coll
            else:
                if 'coll_metadata' not in coll:
                    coll['coll_metadata'] = {}
                coll['coll_metadata']['bytes'] = 1
                coll['coll_metadata']['availability'] = 1
                coll['coll_metadata']['events'] = 1
                coll['coll_metadata']['is_open'] = True
                coll['coll_metadata']['run_number'] = 1
                coll['coll_metadata']['did_type'] = 'DATASET'
                coll['coll_metadata']['list_all_files'] = False

                if (not self.dependency_map_deleted and not self.dependency_map):
                    coll['coll_metadata']['is_open'] = False
                if 'is_open' in coll['coll_metadata'] and not coll['coll_metadata']['is_open']:
                    coll_status = CollectionStatus.Closed
                else:
                    coll_status = CollectionStatus.Open
                coll['status'] = coll_status
                coll['coll_type'] = CollectionType.Dataset

                return coll
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            raise exceptions.IDDSException('%s: %s' % (str(ex), traceback.format_exc()))

    def get_input_collections(self):
        """
        *** Function called by Transformer agent.
        """
        colls = [self.primary_input_collection] + self.other_input_collections
        for coll_int_id in colls:
            coll = self.collections[coll_int_id]
            # if self.is_internal_collection(coll):
            #     coll = self.poll_internal_collection(coll)
            # else:
            #     coll = self.poll_external_collection(coll)
            coll = self.poll_external_collection(coll)
            self.collections[coll_int_id] = coll
        return super(DomaLSSTWork, self).get_input_collections()

    def get_mapped_inputs(self, mapped_input_output_maps):
        ret = []
        for map_id in mapped_input_output_maps:
            inputs = mapped_input_output_maps[map_id]['inputs']

            # if 'primary' is not set, the first one is the primary input.
            primary_input = inputs[0]
            for ip in inputs:
                if 'primary' in ip['content_metadata'] and ip['content_metadata']['primary']:
                    primary_input = ip
            ret.append(primary_input)
        return ret

    def get_mapped_outputs(self, mapped_input_output_maps):
        ret = []
        for map_id in mapped_input_output_maps:
            outputs = mapped_input_output_maps[map_id]['outputs']

            # if 'primary' is not set, the first one is the primary input.
            primary_output = outputs[0]
            for ip in outputs:
                if 'primary' in ip['content_metadata'] and ip['content_metadata']['primary']:
                    primary_output = ip
            ret.append(primary_output)
        return ret

    def map_file_to_content(self, coll_id, scope, name):
        content = {'coll_id': coll_id,
                   'scope': scope,
                   'name': name,  # or a different file name from the dataset name
                   'bytes': 1,
                   'adler32': '12345678',
                   'min_id': 0,
                   'max_id': 1,
                   'content_type': ContentType.File,
                   # 'content_relation_type': content_relation_type,
                   # here events is all events for eventservice, not used here.
                   'content_metadata': {'events': 1}}
        return content

    def is_all_dependency_tasks_available(self, inputs_dependency, task_name_to_coll_map):
        for input_d in inputs_dependency:
            task_name = input_d['task']
            if task_name not in task_name_to_coll_map:
                return False
        return True

    def get_new_input_output_maps(self, mapped_input_output_maps={}):
        """
        *** Function called by Transformer agent.
        New inputs which are not yet mapped to outputs.

        :param mapped_input_output_maps: Inputs that are already mapped.
        """
        new_input_output_maps = {}

        if (not self.dependency_map_deleted and not self.dependency_map
            and self.collections[self.primary_input_collection]['status'] in [CollectionStatus.Closed]):  # noqa: W503
            self.set_has_new_inputs(False)
            return new_input_output_maps

        if self.dependency_map_deleted:
            local_dependency_map_deleted = self.dependency_map_deleted
            self.dependency_map_deleted = []

            mapped_outputs = self.get_mapped_outputs(mapped_input_output_maps)
            mapped_outputs_name = [ip['name'] for ip in mapped_outputs]
            for job in local_dependency_map_deleted:
                output_name = job['name']
                if output_name not in mapped_outputs_name:
                    # this job is not added to db in last round, will do it again.
                    self.dependency_map.append(job)

        if self.dependency_map:
            mapped_keys = mapped_input_output_maps.keys()
            if mapped_keys:
                next_key = max(mapped_keys) + 1
            else:
                next_key = 1

            input_coll = self.get_input_collections()[0]
            input_coll_id = input_coll['coll_id']
            output_coll = self.get_output_collections()[0]
            output_coll_id = output_coll['coll_id']

            task_name_to_coll_map = self.get_work_name_to_coll_map()

            local_dependency_map = self.dependency_map
            self.dependency_map = []
            for job in local_dependency_map:
                output_name = job['name']
                inputs_dependency = job["dependencies"]

                if self.is_all_dependency_tasks_available(inputs_dependency, task_name_to_coll_map):
                    input_content = self.map_file_to_content(input_coll_id, input_coll['scope'], output_name)
                    output_content = self.map_file_to_content(output_coll_id, output_coll['scope'], output_name)
                    new_input_output_maps[next_key] = {'inputs_dependency': [],
                                                       'logs': [],
                                                       'inputs': [input_content],
                                                       'outputs': [output_content]}
                    for input_d in inputs_dependency:
                        task_name = input_d['task']
                        input_name = input_d['inputname']
                        input_d_coll = task_name_to_coll_map[task_name]['outputs'][0]
                        input_d_content = self.map_file_to_content(input_d_coll['coll_id'], input_d_coll['scope'], input_name)
                        new_input_output_maps[next_key]['inputs_dependency'].append(input_d_content)

                    # all inputs are parsed. move it to dependency_map_deleted
                    self.dependency_map_deleted.append(job)
                    next_key += 1
                else:
                    # not all inputs for this job can be parsed.
                    self.dependency_map.append(job)

        self.logger.debug("get_new_input_output_maps, new_input_output_maps: %s" % str(new_input_output_maps))
        return new_input_output_maps

    def use_dependency_to_release_jobs(self):
        """
        *** Function called by Transformer agent.
        """
        return True

    def get_processing(self, input_output_maps):
        """
        *** Function called by Transformer agent.

        If there is already an active processing for this work, will do nothing.
        If there is no active processings, create_processing will be called.
        """
        if self.active_processings:
            return self.processings[self.active_processings[0]]
        else:
            # return None
            return self.create_processing(input_output_maps)

    def create_processing(self, input_output_maps):
        """
        *** Function called by Transformer agent.

        :param input_output_maps: new maps from inputs to outputs.
        """
        # avoid duplicated task name
        self.task_name = self.task_name + "_" + str(self.get_work_id())

        in_files = []
        for map_id in input_output_maps:
            # one map is a job which transform the inputs to outputs.
            inputs = input_output_maps[map_id]['inputs']
            # outputs = input_output_maps[map_id]['outputs']
            for ip in inputs:
                in_files.append(ip['name'])
        for job in self.dependency_map:
            in_files.append(job['name'])

        task_param_map = {}
        task_param_map['vo'] = 'wlcg'
        task_param_map['site'] = self.queue
        task_param_map['workingGroup'] = 'lsst'
        task_param_map['nFilesPerJob'] = 1
        task_param_map['nFiles'] = len(in_files)
        task_param_map['noInput'] = True
        task_param_map['pfnList'] = in_files
        task_param_map['taskName'] = self.task_name
        task_param_map['userName'] = 'iDDS'
        task_param_map['taskPriority'] = 900
        task_param_map['architecture'] = ''
        task_param_map['transUses'] = ''
        task_param_map['transHome'] = None
        task_param_map['transPath'] = 'https://atlpan.web.cern.ch/atlpan/bash-c'
        task_param_map['processingType'] = self.processingType
        task_param_map['prodSourceLabel'] = self.prodSourceLabel
        task_param_map['taskType'] = self.task_type
        task_param_map['coreCount'] = self.core_count
        task_param_map['skipScout'] = True
        task_param_map['cloud'] = 'US'
        task_param_map['inputPreStaging'] = True
        task_param_map['prestagingRuleID'] = 123
        task_param_map['nChunksToWait'] = 1
        task_param_map['maxCpuCount'] = self.maxWalltime
        task_param_map['maxWalltime'] = self.maxWalltime
        task_param_map['maxFailure'] = self.maxAttempt
        task_param_map['maxAttempt'] = self.maxAttempt
        task_param_map['jobParameters'] = [
            {'type': 'constant',
             'value': self.executable,  # noqa: E501
             },
        ]

        proc = {'processing_metadata': {'internal_id': str(uuid.uuid1()),
                                        'task_id': None,
                                        'task_param': task_param_map}}
        self.add_processing_to_processings(proc)
        self.active_processings.append(proc['processing_metadata']['internal_id'])
        return proc

    def submit_panda_task(self, processing):
        try:
            from pandatools import Client

            task_param = processing['processing_metadata']['task_param']
            return_code = Client.insertTaskParams(task_param, verbose=True)
            if return_code[0] == 0:
                return return_code[1][1]
            else:
                self.logger.warn("submit_panda_task, return_code: %s" % str(return_code))
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            # raise exceptions.AgentPluginError('%s: %s' % (str(ex), traceback.format_exc()))
        return None

    def submit_processing(self, processing):
        """
        *** Function called by Carrier agent.
        """
        if 'task_id' in processing['processing_metadata'] and processing['processing_metadata']['task_id']:
            pass
        else:
            task_id = self.submit_panda_task(processing)
            processing['processing_metadata']['task_id'] = task_id
            processing['processing_metadata']['workload_id'] = task_id

    def get_panda_task_id(self, processing):
        from pandatools import Client

        start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=10)
        start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
        status, results = Client.getJobIDsJediTasksInTimeRange(start_time, task_type=self.task_type, verbose=False)
        if status != 0:
            self.logger.warn("Error to poll latest tasks in last ten hours: %s, %s" % (status, results))
            return None

        task_id = None
        for req_id in results:
            task_name = results[req_id]['taskName']
            if processing['processing_metadata']['task_id'] is None and task_name == self.task_name:
                task_id = results[req_id]['jediTaskID']
                processing['processing_metadata']['task_id'] = task_id
                processing['processing_metadata']['workload_id'] = task_id
        return task_id

    def poll_panda_task_status(self, processing):
        if 'task_id' in processing['processing_metadata']:
            from pandatools import Client

            status, task_status = Client.getTaskStatus(processing['processing_metadata']['task_id'])
            if status == 0:
                return task_status
        else:
            return 'failed'
        return None

    def get_processing_status_from_panda_status(self, task_status):
        if task_status in ['registered', 'defined', 'assigning']:
            processing_status = ProcessingStatus.Submitting
        elif task_status in ['ready', 'pending', 'scouting', 'scouted', 'prepared', 'topreprocess', 'preprocessing']:
            processing_status = ProcessingStatus.Submitted
        elif task_status in ['running', 'toretry', 'toincexec', 'throttled']:
            processing_status = ProcessingStatus.Running
        elif task_status in ['done']:
            processing_status = ProcessingStatus.Finished
        elif task_status in ['finished', 'paused']:
            # finished, finishing, waiting it to be done
            processing_status = ProcessingStatus.SubFinished
        elif task_status in ['failed', 'aborted', 'broken', 'exhausted']:
            # aborting, tobroken
            processing_status = ProcessingStatus.Failed
        else:
            # finished, finishing, aborting, topreprocess, preprocessing, tobroken
            # toretry, toincexec, rerefine, paused, throttled, passed
            processing_status = ProcessingStatus.Submitted
        return processing_status

    def sort_panda_jobids(self, input_output_maps):
        panda_job_ids = {}
        panda_id_to_map_ids = {}
        map_id_without_panda_ids = []
        for map_id in input_output_maps:
            outputs = input_output_maps[map_id]['outputs']
            for content in outputs:
                if content['status'] not in panda_job_ids:
                    panda_job_ids[content['status']] = []

                if 'panda_id' in content['content_metadata']:
                    panda_job_ids[content['status']].append(content['content_metadata']['panda_id'])
                    panda_id_to_map_ids[content['content_metadata']['panda_id']] = map_id
                else:
                    map_id_without_panda_ids.append(map_id)

        return panda_job_ids, map_id_without_panda_ids, panda_id_to_map_ids

    def get_registered_panda_jobids(self, input_output_maps):
        panda_job_ids, map_id_without_panda_ids, panda_id_to_map_ids = self.sort_panda_jobids(input_output_maps)
        unterminated_panda_ids = []
        finished_panda_ids = []
        failed_panda_ids = []
        for key in panda_job_ids:
            if key in [ContentStatus.Available]:
                finished_panda_ids += panda_job_ids[key]
            elif key in [ContentStatus.Failed, ContentStatus.FinalFailed, ContentStatus.Lost, ContentStatus.Deleted]:
                failed_panda_ids += panda_job_ids[key]
            else:
                unterminated_panda_ids += panda_job_ids[key]
        return finished_panda_ids + failed_panda_ids, unterminated_panda_ids, map_id_without_panda_ids, panda_id_to_map_ids

    def get_map_id_from_input(self, input_output_maps, input_file):
        map_keys = list(input_output_maps.keys())
        map_keys.reverse()
        for map_id in map_keys:
            inputs = input_output_maps[map_id]['inputs']
            # outputs = input_output_maps[map_id]['outputs']
            for content in inputs:
                if content['name'] == input_file:
                    return map_id
        return None

    def get_content_status_from_panda_status(self, jobstatus):
        if jobstatus == 'finished':
            return ContentStatus.Available
        elif jobstatus == 'failed':
            return ContentStatus.Failed
        else:
            return ContentStatus.Processing

    def get_update_contents_from_map_id(self, map_id, input_output_maps, job_info):
        outputs = input_output_maps[map_id]['outputs']
        update_contents = []
        for content in outputs:
            status = self.get_content_status_from_panda_status(job_info.jobStatus)
            content['substatus'] = status

            if 'panda_id' in content['content_metadata'] and content['content_metadata']['panda_id']:
                if content['content_metadata']['panda_id'] != job_info.PandaID:
                    if 'old_panda_id' not in content['content_metadata']:
                        content['content_metadata']['old_panda_id'] = []
                    content['content_metadata']['old_panda_id'].append(content['content_metadata']['panda_id'])
            content['content_metadata']['panda_id'] = job_info.PandaID

            update_contents.append(content)
        return update_contents

    def map_panda_ids(self, unregistered_job_ids, input_output_maps):
        self.logger.debug("map_panda_ids, unregistered_job_ids: %s" % str(unregistered_job_ids))
        from pandatools import Client

        # updated_map_ids = []
        full_update_contents = []
        chunksize = 2000
        chunks = [unregistered_job_ids[i:i + chunksize] for i in range(0, len(unregistered_job_ids), chunksize)]
        for chunk in chunks:
            jobs_list = Client.getJobStatus(chunk, verbose=0)[1]
            for job_info in jobs_list:
                if job_info.Files and len(job_info.Files) > 0:
                    input_file = job_info.Files[0].lfn.split(':')[1]
                    map_id = self.get_map_id_from_input(input_output_maps, input_file)
                    update_contents = self.get_update_contents_from_map_id(map_id, input_output_maps, job_info)
                    full_update_contents += update_contents
        return full_update_contents

    def get_status_changed_contents(self, unterminated_job_ids, input_output_maps, panda_id_to_map_ids):
        self.logger.debug("get_status_changed_contents, unterminated_job_ids: %s" % str(unterminated_job_ids))
        from pandatools import Client

        full_update_contents = []
        chunksize = 2000
        chunks = [unterminated_job_ids[i:i + chunksize] for i in range(0, len(unterminated_job_ids), chunksize)]
        for chunk in chunks:
            jobs_list = Client.getJobStatus(chunk, verbose=0)[1]
            for job_info in jobs_list:
                panda_id = job_info.PandaID
                map_id = panda_id_to_map_ids[panda_id]
                update_contents = self.get_update_contents_from_map_id(map_id, input_output_maps, job_info)
                full_update_contents += update_contents
        return full_update_contents

    def poll_panda_task(self, processing=None, input_output_maps=None):
        task_id = None
        try:
            from pandatools import Client

            jobs_ids = None
            if processing:
                task_id = processing['processing_metadata']['task_id']
                if task_id is None:
                    self.get_panda_task_id(processing)

                # ret_ids = Client.getPandaIDsWithTaskID(task_id, verbose=False)
                task_info = Client.getJediTaskDetails({'jediTaskID': task_id}, True, True, verbose=False)
                self.logger.info("poll_panda_task, task_info: %s" % str(task_info))
                if task_info[0] != 0:
                    self.logger.warn("poll_panda_task %s, error getting task status, task_info: %s" % (task_id, str(task_info)))
                    # return "No status", {}
                    return ProcessingStatus.Submitting, {}

                task_info = task_info[1]

                processing_status = self.get_processing_status_from_panda_status(task_info["status"])

                jobs_ids = task_info['PandaID']
                ret_get_registered_panda_jobids = self.get_registered_panda_jobids(input_output_maps)
                terminated_job_ids, unterminated_job_ids, map_id_without_panda_ids, panda_id_to_map_ids = ret_get_registered_panda_jobids

                registered_job_ids = terminated_job_ids + unterminated_job_ids
                unregistered_job_ids = []
                for job_id in jobs_ids:
                    if job_id not in registered_job_ids:
                        unregistered_job_ids.append(job_id)

                map_update_contents = self.map_panda_ids(unregistered_job_ids, input_output_maps)
                status_changed_update_contents = self.get_status_changed_contents(unterminated_job_ids, input_output_maps, panda_id_to_map_ids)

                return processing_status, map_update_contents + status_changed_update_contents
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            raise exceptions.IDDSException(msg)
        return ProcessingStatus.Submitting, []

    def kill_processing(self, processing):
        try:
            if processing:
                from pandatools import Client
                task_id = processing['processing_metadata']['task_id']
                Client.killTask(task_id)
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            raise exceptions.IDDSException(msg)

    def reactivate_processing(self, processing):
        try:
            if processing:
                from pandatools import Client
                task_id = processing['processing_metadata']['task_id']
                Client.retryTask(task_id)
                # Client.reactivateTask(task_id)
                # Client.resumeTask(task_id)
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            raise exceptions.IDDSException(msg)

    def poll_processing_updates(self, processing, input_output_maps):
        """
        *** Function called by Carrier agent.
        """
        updated_contents = []
        update_processing = {}
        # self.logger.debug("poll_processing_updates, input_output_maps: %s" % str(input_output_maps))

        if processing:
            if self.tocancel:
                self.logger.info("Cancelling processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], processing['processing_metadata']['task_id']))
                self.kill_processing(processing)
                self.tocancel = False
            elif self.tosuspend:
                self.logger.info("Suspending processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], processing['processing_metadata']['task_id']))
                self.kill_processing(processing)
                self.tosuspend = False
            elif self.toresume:
                self.logger.info("Resuming processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], processing['processing_metadata']['task_id']))
                self.reactivate_processing(processing)
                self.toresume = False
            elif self.is_processing_expired(processing):
                self.logger.info("Expiring processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], processing['processing_metadata']['task_id']))
                self.kill_processing(processing)

            processing_status, poll_updated_contents = self.poll_panda_task(processing=processing, input_output_maps=input_output_maps)
            self.logger.debug("poll_processing_updates, processing_status: %s" % str(processing_status))
            self.logger.debug("poll_processing_updates, update_contents: %s" % str(poll_updated_contents))

            for content in poll_updated_contents:
                updated_content = {'content_id': content['content_id'],
                                   'substatus': content['substatus'],
                                   'content_metadata': content['content_metadata']}
                updated_contents.append(updated_content)

            content_substatus = {'finished': 0, 'unfinished': 0}
            for map_id in input_output_maps:
                outputs = input_output_maps[map_id]['outputs']
                for content in outputs:
                    if content.get('substatus', ContentStatus.New) != ContentStatus.Available:
                        content_substatus['unfinished'] += 1
                    else:
                        content_substatus['finished'] += 1

            update_processing = {'processing_id': processing['processing_id'],
                                 'parameters': {'status': processing_status}}

        self.logger.debug("poll_processing_updates, task: %i, update_processing: %s" %
                          (processing['processing_metadata']['task_id'], str(update_processing)))
        self.logger.debug("poll_processing_updates, task: %i, updated_contents: %s" %
                          (processing['processing_metadata']['task_id'], str(updated_contents)))
        return update_processing, updated_contents

    def get_status_statistics(self, registered_input_output_maps):
        status_statistics = {}
        for map_id in registered_input_output_maps:
            outputs = registered_input_output_maps[map_id]['outputs']

            for content in outputs:
                if content['status'].name not in status_statistics:
                    status_statistics[content['status'].name] = 0
                status_statistics[content['status'].name] += 1
        self.status_statistics = status_statistics
        self.logger.debug("registered_input_output_maps, status_statistics: %s" % str(status_statistics))
        return status_statistics

    def syn_work_status(self, registered_input_output_maps):
        super(DomaLSSTWork, self).syn_work_status(registered_input_output_maps)
        self.get_status_statistics(registered_input_output_maps)
        self.logger.debug("syn_work_status, self.active_processings: %s" % str(self.active_processings))
        self.logger.debug("syn_work_status, self.has_new_inputs(): %s" % str(self.has_new_inputs()))
        self.logger.debug("syn_work_status, coll_metadata_is_open: %s" %
                          str(self.collections[self.primary_input_collection]['coll_metadata']['is_open']))
        self.logger.debug("syn_work_status, primary_input_collection_status: %s" %
                          str(self.collections[self.primary_input_collection]['status']))

        if self.is_processings_terminated() and not self.has_new_inputs():
            if not self.is_all_outputs_flushed(registered_input_output_maps):
                self.logger.warn("The work processings %s is terminated. but not all outputs are flushed. Wait to flush the outputs then finish the transform" % str(self.get_processing_ids()))
                return

            keys = self.status_statistics.keys()
            if ContentStatus.New.name in keys or ContentStatus.Processing.name in keys:
                pass
            else:
                if len(keys) == 1:
                    if ContentStatus.Available.name in keys:
                        self.status = WorkStatus.Finished
                    else:
                        self.status = WorkStatus.Failed
                else:
                    self.status = WorkStatus.SubFinished
