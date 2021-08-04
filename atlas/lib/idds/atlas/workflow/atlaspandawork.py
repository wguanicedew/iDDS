#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2020 - 2021


try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

import datetime
import os
import random
import traceback

from rucio.client.client import Client as RucioClient
from rucio.common.exception import (CannotAuthenticate as RucioCannotAuthenticate)

from idds.common import exceptions
from idds.common.constants import (TransformType, CollectionStatus, CollectionType,
                                   ContentStatus, ContentType,
                                   ProcessingStatus, WorkStatus)
from idds.common.utils import extract_scope_atlas
from idds.workflow.work import Work, Processing
# from idds.workflow.workflow import Condition


class ATLASPandaWork(Work):
    def __init__(self, task_parameters=None,
                 work_tag='atlas', exec_type='panda', work_id=None,
                 primary_input_collection=None, other_input_collections=None,
                 output_collections=None, log_collections=None,
                 logger=None,
                 # dependency_map=None, task_name="",
                 # task_queue=None, processing_type=None,
                 # prodSourceLabel='test', task_type='test',
                 # maxwalltime=90000, maxattempt=5, core_count=1,
                 # encode_command_line=False,
                 num_retries=5,
                 # task_log=None,
                 # task_cloud=None,
                 # task_rss=0
                 ):

        super(ATLASPandaWork, self).__init__(work_type=TransformType.Processing,
                                             work_tag=work_tag,
                                             exec_type=exec_type,
                                             work_id=work_id,
                                             primary_input_collection=primary_input_collection,
                                             other_input_collections=other_input_collections,
                                             output_collections=output_collections,
                                             log_collections=log_collections,
                                             release_inputs_after_submitting=True,
                                             logger=logger)
        self.panda_url = None
        self.panda_url_ssl = None
        self.panda_monitor = None

        self.task_parameters = None
        self.parse_task_parameters(task_parameters)
        # self.logger.setLevel(logging.DEBUG)

        self.retry_number = 0
        self.num_retries = num_retries

        self.load_panda_urls()

    def my_condition(self):
        if self.is_finished():
            return True
        return False

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
        # self.logger.debug("panda config: %s" % panda_config)
        self.panda_url = None
        self.panda_url_ssl = None
        self.panda_monitor = None

        if panda_config.has_section('panda'):
            if panda_config.has_option('panda', 'panda_monitor_url'):
                self.panda_monitor = panda_config.get('panda', 'panda_monitor_url')
                os.environ['PANDA_MONITOR_URL'] = self.panda_monitor
                # self.logger.debug("Panda monitor url: %s" % str(self.panda_monitor))
            if panda_config.has_option('panda', 'panda_url'):
                self.panda_url = panda_config.get('panda', 'panda_url')
                os.environ['PANDA_URL'] = self.panda_url
                # self.logger.debug("Panda url: %s" % str(self.panda_url))
            if panda_config.has_option('panda', 'panda_url_ssl'):
                self.panda_url_ssl = panda_config.get('panda', 'panda_url_ssl')
                os.environ['PANDA_URL_SSL'] = self.panda_url_ssl
                # self.logger.debug("Panda url ssl: %s" % str(self.panda_url_ssl))

        if not self.panda_monitor and 'PANDA_MONITOR_URL' in os.environ and os.environ['PANDA_MONITOR_URL']:
            self.panda_monitor = os.environ['PANDA_MONITOR_URL']
            # self.logger.debug("Panda monitor url: %s" % str(self.panda_monitor))
        if not self.panda_url and 'PANDA_URL' in os.environ and os.environ['PANDA_URL']:
            self.panda_url = os.environ['PANDA_URL']
            # self.logger.debug("Panda url: %s" % str(self.panda_url))
        if not self.panda_url_ssl and 'PANDA_URL_SSL' in os.environ and os.environ['PANDA_URL_SSL']:
            self.panda_url_ssl = os.environ['PANDA_URL_SSL']
            # self.logger.debug("Panda url ssl: %s" % str(self.panda_url_ssl))

    def set_agent_attributes(self, attrs, req_attributes=None):
        if self.class_name not in attrs or 'life_time' not in attrs[self.class_name] or int(attrs[self.class_name]['life_time']) <= 0:
            attrs['life_time'] = None
        super(ATLASPandaWork, self).set_agent_attributes(attrs)
        if self.agent_attributes and 'num_retries' in self.agent_attributes and self.agent_attributes['num_retries']:
            self.num_retries = int(self.agent_attributes['num_retries'])

    def parse_task_parameters(self, task_parameters):
        if self.task_parameters:
            return
        elif not task_parameters:
            return
        self.task_parameters = task_parameters

        try:
            if 'taskName' in self.task_parameters:
                self.task_name = self.task_parameters['taskName']
                self.set_work_name(self.task_name)

            if 'jobParameters' in self.task_parameters:
                jobParameters = self.task_parameters['jobParameters']
                for jobPs in jobParameters:
                    if type(jobPs) in [tuple, list]:
                        for jobP in jobPs:
                            if type(jobP) in [dict]:
                                if 'dataset' in jobP and 'param_type' in jobP:
                                    if jobP['param_type'] == 'input':
                                        input_c = jobP['dataset']
                                        scope, name = extract_scope_atlas(input_c, scopes=[])
                                        input_coll = {'scope': scope, 'name': name}
                                        self.set_primary_input_collection(input_coll)
                                    if jobP['param_type'] == 'output':
                                        output_c = jobP['dataset']
                                        scope, name = extract_scope_atlas(output_c, scopes=[])
                                        output_coll = {'scope': scope, 'name': name}
                                        self.add_output_collections([output_coll])

            if 'log' in self.task_parameters:
                log = self.task_parameters['log']
                dataset = log['dataset']
                scope, name = extract_scope_atlas(dataset, scopes=[])
                log_col = {'scope': scope, 'name': name}
                self.add_log_collections(log_col)

            if not self.get_primary_input_collection():
                output_colls = self.get_output_collections()
                output_coll = output_colls[0]
                name = 'pseudo_input.' + datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S_%f") + str(random.randint(1, 1000))
                input_coll = {'scope': output_coll.scope, 'name': name, 'type': CollectionType.PseudoDataset}
                self.set_primary_input_collection(input_coll)

        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            # raise exceptions.IDDSException('%s: %s' % (str(ex), traceback.format_exc()))
            self.add_errors(str(ex))

    def get_rucio_client(self):
        try:
            client = RucioClient()
        except RucioCannotAuthenticate as error:
            self.logger.error(error)
            self.logger.error(traceback.format_exc())
            raise exceptions.IDDSException('%s: %s' % (str(error), traceback.format_exc()))
        return client

    def poll_external_collection(self, coll):
        try:
            if coll.status in [CollectionStatus.Closed]:
                return coll
            else:
                if coll.coll_type == CollectionType.PseudoDataset:
                    coll.coll_metadata['bytes'] = 0
                    coll.coll_metadata['total_files'] = 0
                    coll.coll_metadata['availability'] = True
                    coll.coll_metadata['events'] = 0
                    coll.coll_metadata['is_open'] = False
                    coll.coll_metadata['run_number'] = None
                    coll.coll_metadata['did_type'] = 'DATASET'
                    coll.coll_metadata['list_all_files'] = False

                    if 'is_open' in coll.coll_metadata and not coll.coll_metadata['is_open']:
                        coll_status = CollectionStatus.Closed
                    else:
                        coll_status = CollectionStatus.Open
                    coll.status = coll_status

                    coll.coll_metadata['coll_type'] = coll.coll_type

                    return coll
                else:
                    client = self.get_rucio_client()
                    did_meta = client.get_metadata(scope=coll.scope, name=coll.name)

                    coll.coll_metadata['bytes'] = did_meta['bytes']
                    coll.coll_metadata['total_files'] = did_meta['length']
                    coll.coll_metadata['availability'] = did_meta['availability']
                    coll.coll_metadata['events'] = did_meta['events']
                    coll.coll_metadata['is_open'] = did_meta['is_open']
                    coll.coll_metadata['run_number'] = did_meta['run_number']
                    coll.coll_metadata['did_type'] = did_meta['did_type']
                    coll.coll_metadata['list_all_files'] = False

                    if 'is_open' in coll.coll_metadata and not coll.coll_metadata['is_open']:
                        coll_status = CollectionStatus.Closed
                    else:
                        coll_status = CollectionStatus.Open
                    coll.status = coll_status

                    if 'did_type' in coll.coll_metadata:
                        if coll.coll_metadata['did_type'] == 'DATASET':
                            coll_type = CollectionType.Dataset
                        elif coll.coll_metadata['did_type'] == 'CONTAINER':
                            coll_type = CollectionType.Container
                        else:
                            coll_type = CollectionType.File
                    else:
                        coll_type = CollectionType.Dataset
                    coll.coll_metadata['coll_type'] = coll_type
                    coll.coll_type = coll_type
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
        return super(ATLASPandaWork, self).get_input_collections()

    def get_input_contents(self):
        """
        Get all input contents from DDM.
        """
        try:
            ret_files = []
            return ret_files
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            raise exceptions.IDDSException('%s: %s' % (str(ex), traceback.format_exc()))

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

    def get_next_map_id(self, input_output_maps):
        mapped_keys = input_output_maps.keys()
        if mapped_keys:
            next_key = max(mapped_keys) + 1
        else:
            next_key = 1
        return next_key

    def get_new_input_output_maps(self, mapped_input_output_maps={}):
        """
        *** Function called by Transformer agent.
        New inputs which are not yet mapped to outputs.

        :param mapped_input_output_maps: Inputs that are already mapped.
        """
        inputs = self.get_input_contents()
        mapped_inputs = self.get_mapped_inputs(mapped_input_output_maps)
        mapped_inputs_scope_name = [ip['scope'] + ":" + ip['name'] for ip in mapped_inputs]

        new_inputs = []
        new_input_output_maps = {}
        for ip in inputs:
            ip_scope_name = ip['scope'] + ":" + ip['name']
            if ip_scope_name not in mapped_inputs_scope_name:
                new_inputs.append(ip)

        # to avoid cheking new inputs if there are no new inputs anymore
        if (not new_inputs and self.collections[self.primary_input_collection].status in [CollectionStatus.Closed]):  # noqa: W503
            self.set_has_new_inputs(False)
        else:
            pass

        # self.logger.debug("get_new_input_output_maps, new_input_output_maps: %s" % str(new_input_output_maps))
        self.logger.debug("get_new_input_output_maps, new_input_output_maps len: %s" % len(new_input_output_maps))
        return new_input_output_maps

    def use_dependency_to_release_jobs(self):
        """
        *** Function called by Transformer agent.
        """
        return False

    def get_processing(self, input_output_maps=[], without_creating=False):
        """
        *** Function called by Transformer agent.

        If there is already an active processing for this work, will do nothing.
        If there is no active processings, create_processing will be called.
        """
        if self.active_processings:
            return self.processings[self.active_processings[0]]
        else:
            if not without_creating:
                # return None
                return self.create_processing(input_output_maps)
        return None

    def create_processing(self, input_output_maps=[]):
        """
        *** Function called by Transformer agent.

        :param input_output_maps: new maps from inputs to outputs.
        """
        processing_metadata = {'task_param': self.task_parameters}
        proc = Processing(processing_metadata=processing_metadata)
        proc.workload_id = None
        self.add_processing_to_processings(proc)
        self.active_processings.append(proc.internal_id)
        return proc

    def submit_panda_task(self, processing):
        try:
            from pandatools import Client

            proc = processing['processing_metadata']['processing']
            task_param = proc.processing_metadata['task_param']
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
        proc = processing['processing_metadata']['processing']
        if proc.workload_id:
            # if 'task_id' in processing['processing_metadata'] and processing['processing_metadata']['task_id']:
            pass
        else:
            task_id = self.submit_panda_task(processing)
            # processing['processing_metadata']['task_id'] = task_id
            # processing['processing_metadata']['workload_id'] = task_id
            proc.workload_id = task_id
            if task_id:
                proc.submitted_at = datetime.datetime.utcnow()

    def poll_panda_task_status(self, processing):
        if 'processing' in processing['processing_metadata']:
            from pandatools import Client

            proc = processing['processing_metadata']['processing']
            status, task_status = Client.getTaskStatus(proc.workload_id)
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

    def get_panda_task_id(self, processing):
        from pandatools import Client

        start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=10)
        start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
        status, results = Client.getJobIDsJediTasksInTimeRange(start_time, task_type=self.task_type, verbose=False)
        if status != 0:
            self.logger.warn("Error to poll latest tasks in last ten hours: %s, %s" % (status, results))
            return None

        proc = processing['processing_metadata']['processing']
        task_id = None
        for req_id in results:
            task_name = results[req_id]['taskName']
            if proc.workload_id is None and task_name == self.task_name:
                task_id = results[req_id]['jediTaskID']
                # processing['processing_metadata']['task_id'] = task_id
                # processing['processing_metadata']['workload_id'] = task_id
                proc.workload_id = task_id
                if task_id:
                    proc.submitted_at = datetime.datetime.utcnow()

        return task_id

    def poll_panda_task(self, processing=None, input_output_maps=None):
        task_id = None
        try:
            from pandatools import Client

            if processing:
                proc = processing['processing_metadata']['processing']
                task_id = proc.workload_id
                if task_id is None:
                    task_id = self.get_panda_task_id(processing)

                if task_id:
                    # ret_ids = Client.getPandaIDsWithTaskID(task_id, verbose=False)
                    task_info = Client.getJediTaskDetails({'jediTaskID': task_id}, True, True, verbose=False)
                    self.logger.info("poll_panda_task, task_info: %s" % str(task_info))
                    if task_info[0] != 0:
                        self.logger.warn("poll_panda_task %s, error getting task status, task_info: %s" % (task_id, str(task_info)))
                        return ProcessingStatus.Submitting, {}

                    task_info = task_info[1]

                    processing_status = self.get_processing_status_from_panda_status(task_info["status"])

                    if processing_status in [ProcessingStatus.SubFinished]:
                        if self.retry_number < self.num_retries:
                            self.reactivate_processing(processing)
                            processing_status = ProcessingStatus.Submitted
                            self.retry_number += 1

                    return processing_status, [], {}
                else:
                    return ProcessingStatus.Failed, [], {}
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            self.logger.error(msg)
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            # raise exceptions.IDDSException(msg)
        return ProcessingStatus.Submitting, [], {}

    def kill_processing(self, processing):
        try:
            if processing:
                from pandatools import Client
                proc = processing['processing_metadata']['processing']
                task_id = proc.workload_id
                # task_id = processing['processing_metadata']['task_id']
                # Client.killTask(task_id)
                Client.finishTask(task_id, soft=False)
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            raise exceptions.IDDSException(msg)

    def kill_processing_force(self, processing):
        try:
            if processing:
                from pandatools import Client
                proc = processing['processing_metadata']['processing']
                task_id = proc.workload_id
                # task_id = processing['processing_metadata']['task_id']
                Client.killTask(task_id)
                # Client.finishTask(task_id, soft=True)
        except Exception as ex:
            msg = "Failed to check the processing (%s) status: %s" % (str(processing['processing_id']), str(ex))
            raise exceptions.IDDSException(msg)

    def reactivate_processing(self, processing):
        try:
            if processing:
                from pandatools import Client
                # task_id = processing['processing_metadata']['task_id']
                proc = processing['processing_metadata']['processing']
                task_id = proc.workload_id

                # Client.retryTask(task_id)
                status, out = Client.retryTask(task_id, newParams={})
                self.logger.warn("Retry processing(%s) with task id(%s): %s, %s" % (processing['processing_id'], task_id, status, out))
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
        reset_expired_at = False
        reactive_contents = []
        # self.logger.debug("poll_processing_updates, input_output_maps: %s" % str(input_output_maps))

        if processing:
            proc = processing['processing_metadata']['processing']
            if proc.tocancel:
                self.logger.info("Cancelling processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.kill_processing_force(processing)
                # self.kill_processing(processing)
                proc.tocancel = False
                proc.polling_retries = 0
            elif proc.tosuspend:
                self.logger.info("Suspending processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.kill_processing_force(processing)
                # self.kill_processing(processing)
                proc.tosuspend = False
                proc.polling_retries = 0
            elif proc.toresume:
                self.logger.info("Resuming processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.reactivate_processing(processing)
                reset_expired_at = True
                proc.toresume = False
                proc.polling_retries = 0
                proc.has_new_updates()
                # reactive_contents = self.reactive_contents(input_output_maps)
            # elif self.is_processing_expired(processing):
            elif proc.toexpire:
                self.logger.info("Expiring processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.kill_processing(processing)
                proc.toexpire = False
                proc.polling_retries = 0
            elif proc.tofinish or proc.toforcefinish:
                self.logger.info("Finishing processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.kill_processing(processing)
                proc.tofinish = False
                proc.toforcefinish = False
                proc.polling_retries = 0
            elif self.is_all_contents_terminated_and_with_missing(input_output_maps):
                self.logger.info("All contents terminated(There are Missing contents). Finishing processing (processing id: %s, jediTaskId: %s)" % (processing['processing_id'], proc.workload_id))
                self.kill_processing(processing)

            processing_status, poll_updated_contents, new_input_output_maps = self.poll_panda_task(processing=processing, input_output_maps=input_output_maps)
            self.logger.debug("poll_processing_updates, processing_status: %s" % str(processing_status))
            self.logger.debug("poll_processing_updates, update_contents: %s" % str(poll_updated_contents))

            if poll_updated_contents:
                proc.has_new_updates()
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

            if processing_status in [ProcessingStatus.SubFinished, ProcessingStatus.Finished, ProcessingStatus.Failed] and updated_contents:
                self.logger.info("Processing %s is terminated, but there are still contents to be flushed. Waiting." % (proc.workload_id))
                # there are still polling contents, should not terminate the task.
                processing_status = ProcessingStatus.Running

            if processing_status in [ProcessingStatus.SubFinished] and content_substatus['finished'] > 0 and content_substatus['unfinished'] == 0:
                # found that a 'done' panda task has got a 'finished' status. Maybe in this case 'finished' is a transparent status.
                if proc.polling_retries is None:
                    proc.polling_retries = 0

            if processing_status in [ProcessingStatus.SubFinished, ProcessingStatus.Finished, ProcessingStatus.Failed]:
                if proc.polling_retries is not None and proc.polling_retries < 3:
                    self.logger.info("processing %s polling_retries(%s) < 3, keep running" % (processing['processing_id'], proc.polling_retries))
                    processing_status = ProcessingStatus.Running
                    proc.polling_retries += 1
            else:
                proc.polling_retries = 0

            if proc.in_operation_time():
                processing_status = ProcessingStatus.Running

            update_processing = {'processing_id': processing['processing_id'],
                                 'parameters': {'status': processing_status}}
            if reset_expired_at:
                processing['expired_at'] = None
                update_processing['parameters']['expired_at'] = None
                proc.polling_retries = 0
                # if (processing_status in [ProcessingStatus.SubFinished, ProcessingStatus.Finished, ProcessingStatus.Failed]
                #     or processing['status'] in [ProcessingStatus.Resuming]):   # noqa W503
                # using polling_retries to poll it again when panda may update the status in a delay(when issuing retryTask, panda will not update it without any delay).
                update_processing['parameters']['status'] = ProcessingStatus.Resuming
            proc.status = update_processing['parameters']['status']

        self.logger.debug("poll_processing_updates, task: %s, update_processing: %s" %
                          (proc.workload_id, str(update_processing)))
        self.logger.debug("poll_processing_updates, task: %s, updated_contents: %s" %
                          (proc.workload_id, str(updated_contents)))
        self.logger.debug("poll_processing_updates, task: %s, reactive_contents: %s" %
                          (proc.workload_id, str(reactive_contents)))
        return update_processing, updated_contents + reactive_contents, new_input_output_maps

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

    def syn_work_status(self, registered_input_output_maps, all_updates_flushed=True, output_statistics={}, to_release_input_contents=[]):
        super(ATLASPandaWork, self).syn_work_status(registered_input_output_maps, all_updates_flushed, output_statistics, to_release_input_contents)
        # self.get_status_statistics(registered_input_output_maps)
        self.status_statistics = output_statistics

        self.logger.debug("syn_work_status, self.active_processings: %s" % str(self.active_processings))
        self.logger.debug("syn_work_status, self.has_new_inputs(): %s" % str(self.has_new_inputs))
        self.logger.debug("syn_work_status, coll_metadata_is_open: %s" %
                          str(self.collections[self.primary_input_collection].coll_metadata['is_open']))
        self.logger.debug("syn_work_status, primary_input_collection_status: %s" %
                          str(self.collections[self.primary_input_collection].status))

        self.logger.debug("syn_work_status(%s): is_processings_terminated: %s" % (str(self.get_processing_ids()), str(self.is_processings_terminated())))
        self.logger.debug("syn_work_status(%s): is_input_collections_closed: %s" % (str(self.get_processing_ids()), str(self.is_input_collections_closed())))
        self.logger.debug("syn_work_status(%s): has_new_inputs: %s" % (str(self.get_processing_ids()), str(self.has_new_inputs)))
        self.logger.debug("syn_work_status(%s): has_to_release_inputs: %s" % (str(self.get_processing_ids()), str(self.has_to_release_inputs())))
        self.logger.debug("syn_work_status(%s): to_release_input_contents: %s" % (str(self.get_processing_ids()), str(to_release_input_contents)))

        if self.is_processings_terminated() and self.is_input_collections_closed() and not self.has_new_inputs and not self.has_to_release_inputs() and not to_release_input_contents:
            # if not self.is_all_outputs_flushed(registered_input_output_maps):
            if not all_updates_flushed:
                self.logger.warn("The work processings %s is terminated. but not all outputs are flushed. Wait to flush the outputs then finish the transform" % str(self.get_processing_ids()))
                return

            if self.is_processings_finished():
                self.status = WorkStatus.Finished
            if self.is_processings_failed():
                self.status = WorkStatus.Failed
            elif self.is_processings_subfinished():
                self.status = WorkStatus.SubFinished
        else:
            self.status = WorkStatus.Transforming
