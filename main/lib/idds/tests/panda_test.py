
import os   # noqa E402
import sys
import datetime

os.environ['PANDA_URL'] = 'http://pandaserver-doma.cern.ch:25080/server/panda'
os.environ['PANDA_URL_SSL'] = 'https://pandaserver-doma.cern.ch:25443/server/panda'

from pandaclient import Client  # noqa E402

"""
jobids = [1408118]
jobs_list_status = Client.getJobStatus(jobids, verbose=0)
print(jobs_list_status)
jobs_list = jobs_list_status[1]
print(jobs_list)
for job_info in jobs_list:
    if job_info is not None:
        # if job_info.Files and len(job_info.Files) > 0:
        print(job_info)
        print(job_info.attemptNr)
        print(job_info.maxAttempt)
        print(job_info.Files)
        print(job_info.Files[0])
        for f in job_info.Files:
            # print(dir(f))
            print(f._attributes)
            print(f.values())
            print(f.type)
"""

jediTaskID = 10517    # 10607
jediTaskID = 59725
ret = Client.getJediTaskDetails({'jediTaskID': jediTaskID}, True, True, verbose=False)
print(ret)

# ret = Client.getTaskStatus(jediTaskID, verbose=False)
# print(ret)

task_info = ret[1]
jobids = task_info['PandaID']
ret = Client.getJobStatus(ids=jobids, verbose=False)
print(ret)

if ret[0] == 0:
    jobs = ret[1]
    left_jobids = []
    ret_jobs = []
    print(len(jobs))
    for jobid, jobinfo in zip(jobids, jobs):
        if jobinfo is None:
            left_jobids.append(jobid)
        else:
            ret_jobs.append(jobinfo)
    if left_jobids:
        print(len(left_jobids))
        ret = Client.getFullJobStatus(ids=left_jobids, verbose=False)
        print(ret)
        print(len(ret[1]))
    ret_jobs = ret_jobs + ret[1]
    print(len(ret_jobs))

# sys.exit(0)

"""
jediTaskID = 998
ret = Client.getPandaIDsWithTaskID(jediTaskID, verbose=False)
# print(ret)
jobids = ret[1]
# print(jobids)

ret = Client.getJobStatus(ids=jobids, verbose=False)
print(ret)

ret = Client.getFullJobStatus(ids=jobids, verbose=False)
# print(ret)

ret = Client.getJediTaskDetails({'jediTaskID': jediTaskID}, True, True, verbose=False)
print(ret)
"""

task_ids = []
# task_ids = [1565, 1566, 1567, 1568, 1570, 1572, 1575, 1576, 1579, 1580, 1581, 1582, 1584, 1585, 1586, 1587, 1588, 1589, 1590, 1591, 1592, 1593, 1597, 1598, 1599, 1601, 1602, 1603, 1604, 1607, 1608, 1609, 1610, 1611, 1612, 1613, 1617]
# task_ids = [i for i in range(1091, 1104)] + [i for i in range(1274, 1392)]
# task_ids = [812]
# task_ids += [i for i in range(815, 822)]
# task_ids = [827, 830, 913, 914, 916, 917, 1030, 1031, 1033, 1034, 1036, 1048, 1090, 1392]
# task_ids += [i for i in range(833, 839)]
# task_ids += [i for i in range(1048, 1078)]
# task_ids = [i for i in range(1855, 1856)]
# task_ids = [i for i in range(1840, 1850)] + [i for i in range(1990, 2000)]
# task_ids = [2549, 2560]
# task_ids = [i for i in range(3692, 3723)]
# task_ids = [3834, 3835, 3836]
# task_ids = [i for i in range(141294, 142200)] + [i for i in range(141003, 141077)] + [i for i in range(141145, 141255)]
# task_ids = [140954, 140955, 142228]
# task_ids = [i for i in range(142507, 142651)]
# task_ids = [i for i in range(140349, 140954)] + [142268, 142651]
# task_ids = [1851] + [i for i in range(4336, 4374)] + [i for i in range(133965, 136025)]
task_ids = [832, 2347, 3045, 66860, 67036] + [i for i in range(121273, 140349)]
for task_id in task_ids:
    print("Killing %s" % task_id)
    Client.killTask(task_id)

"""
jobids = []
Client.getJobStatus(ids=jobids, verbose=False)

Client.getJediTaskDetails(taskDict,fullFlag,withTaskInfo,verbose=False)

Client.getFullJobStatus(ids, verbose=False)
"""

# getJobIDsJediTasksInTimeRange(timeRange, dn=None, minTaskID=None, verbose=False, task_type='user')
# /DC=ch/DC=cern/OU=Organic Units/OU=Users/CN=atlpilo1/CN=614260/CN=Robot: ATLAS Pilot1

start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=5)
start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
# ret = Client.getJobIDsJediTasksInTimeRange(start_time, verbose=False)
# print(ret)

# ret = Client.getJobIDsJediTasksInTimeRange(start_time, task_type='test', verbose=False)
# print(ret)
# ret = Client.getJobIDsJediTasksInTimeRange(start_time, dn='/DC=ch/DC=cern/OU=Organic Units/OU=Users/CN=atlpilo1/CN=614260/CN=Robot: ATLAS Pilot1', task_type='test', verbose=False)
# print(ret)
# ret = Client.getJobIDsJediTasksInTimeRange(start_time, dn='atlpilo1', task_type='test', verbose=False)
# print(ret)


taskID = 1595
newOpts = {}
# warning for PQ
# site = newOpts.get('site', None)
# excludedSite = newOpts.get('excludedSite', None)
# for JEDI
taskIDs = [10624]
for taskID in taskIDs:
    status, out = Client.retryTask(taskID, verbose=True, properErrorCode=True, newParams=newOpts)
    print(status)
    print(out)

sys.exit(0)
