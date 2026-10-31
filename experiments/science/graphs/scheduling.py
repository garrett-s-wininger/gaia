"""Discrete-event model, not a measured compiler service or OS scheduler."""
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import math
import statistics
import time


@dataclass(frozen=True)
class Task:
    name: str
    client: str
    generation: int
    arrival: int
    work: int
    group: str
    deps: tuple[str,...] = ()
    durable: bool = False


def fixture(period=25, generations=12):
    result=[]
    for client in ('human','agent'):
        for generation in range(1,generations+1):
            at=(generation-1)*period+(0 if client=='human' else 7)
            stem=f'{client}:{generation}';group=f'inputs:{generation%3}'
            result.extend([Task(stem+':parse',client,generation,at,12,group),
                           Task(stem+':diagnostic',client,generation,at,5,group,(stem+':parse',)),
                           Task(stem+':compile',client,generation,at,35,group,(stem+':parse',)),
                           Task(stem+':test',client,generation,at,45,'tests',(stem+':compile',)),
                           Task(stem+':search',client,generation,at,6,'index')])
    for n in range(8):result.append(Task(f'bulk:{n}','bulk',0,n*25,35,'bulk',durable=True))
    return result


def simulate(tasks, policy, workers=4, cancellation=True, quantum=4, cold_cost=5, estimate_error=False):
    byname={t.name:t for t in tasks}
    if len(byname)!=len(tasks) or workers<1 or quantum<1:raise ValueError('model bounds')
    for t in tasks:
        if t.work<1 or t.arrival<0 or any(d not in byname for d in t.deps):raise ValueError('task bounds')
    children=defaultdict(set)
    for t in tasks:
        for dep in t.deps:children[dep].add(t.name)
    active=set()
    def span(name):
        if name in active:raise ValueError('cyclic task graph')
        active.add(name);task=byname[name]
        estimate=task.work*(3 if estimate_error and task.group=='tests' else 1)
        result=estimate+max((span(child) for child in children[name]),default=0)
        active.remove(name);return result
    spans={name:span(name) for name in byname}
    now=0;status={t.name:'future' for t in tasks};latest={};left={};started={};finished={};published=[];queue_wait=[]
    running=[None]*workers;caches=[deque(maxlen=2) for _ in range(workers)];safe_at={}
    score=[defaultdict(float) for _ in range(workers)];last_used=[{} for _ in range(workers)]
    work_spent=Counter();cold_work=0;decisions=0;overhead=0;last_client=None;events=[]
    local_ready=[deque() for _ in range(workers)];enqueued=set()
    def obsolete(t):return not t.durable and t.generation<latest.get(t.client,t.generation)
    def group_score(worker,t):
        age=now-last_used[worker].get(t.group,now)
        return score[worker][t.group]*math.exp(-age/80)
    def ready_names():
        return [t.name for t in tasks if status[t.name]=='queued' and all(status[d]=='done' for d in t.deps)]
    def choose(worker,ready):
        nonlocal last_client
        if policy=='fifo':return min(ready,key=lambda n:(byname[n].arrival,n))
        if policy=='critical':return min(ready,key=lambda n:(-spans[n],byname[n].arrival,n))
        if policy=='fair':
            clients=sorted({byname[n].client for n in ready})
            selected=next((c for c in clients if last_client is None or c>last_client),clients[0]);last_client=selected
            return min((n for n in ready if byname[n].client==selected),key=lambda n:(byname[n].arrival,n))
        if policy=='work-stealing':
            for name in sorted(ready,key=lambda n:(byname[n].arrival,n)):
                if name not in enqueued:
                    home=sum(byname[name].client.encode())%workers
                    local_ready[home].append(name);enqueued.add(name)
            for queue in local_ready:
                while queue and status[queue[0]]!='queued':queue.popleft()
                while queue and status[queue[-1]]!='queued':queue.pop()
            if local_ready[worker]:return local_ready[worker].pop()
            victim=max(range(workers),key=lambda w:len(local_ready[w]))
            return local_ready[victim].popleft()
        if policy=='foraging':
            # Older jobs gain priority even when locality initially favors others.
            return min(ready,key=lambda n:(-(now-byname[n].arrival)/20-group_score(worker,byname[n]),-spans[n],n))
        raise ValueError(policy)
    iterations=0
    while any(value not in ('done','cancelled') for value in status.values()):
        iterations+=1
        if iterations>1000000:raise ValueError('event loop bound')
        for task in tasks:
            if status[task.name]=='future' and task.arrival<=now:
                status[task.name]='queued'
                if not task.durable:latest[task.client]=max(latest.get(task.client,0),task.generation)
                events.append(('arrival',now,task.name))
        if cancellation:
            for task in tasks:
                if status[task.name]=='queued' and (obsolete(task) or any(status[d]=='cancelled' for d in task.deps)):
                    status[task.name]='cancelled';events.append(('cancel-queued',now,task.name))
        for worker in range(workers):
            name=running[worker]
            if name is not None and left[name]==0:
                task=byname[name];status[name]='done';finished[name]=now;running[worker]=None
                if task.durable or not obsolete(task):published.append(name)
                score[worker][task.group]=group_score(worker,task)+1;last_used[worker][task.group]=now
                events.append(('finish',now,name))
            elif name is not None and now>=safe_at[name] and cancellation and obsolete(byname[name]):
                status[name]='cancelled';running[worker]=None;events.append(('cancel-running',now,name))
            elif name is not None and now>=safe_at[name]:
                safe_at[name]=now+min(quantum,left[name])
        begin=time.perf_counter_ns()
        for worker in range(workers):
            if running[worker] is not None:continue
            ready=ready_names()
            if not ready:continue
            name=choose(worker,ready);task=byname[name];decisions+=1;status[name]='running';running[worker]=name
            started[name]=now;queue_wait.append((task.client,now-task.arrival))
            extra=0 if task.group in caches[worker] else cold_cost
            cold_work+=extra
            if task.group in caches[worker]:caches[worker].remove(task.group)
            caches[worker].append(task.group);left[name]=task.work+extra
            safe_at[name]=now+min(quantum,left[name])
            events.append(('start',now,name))
        overhead+=time.perf_counter_ns()-begin
        next_arrival=min((t.arrival for t in tasks if status[t.name]=='future'),default=None)
        if not any(running):
            if next_arrival is None:
                if any(s=='queued' for s in status.values()):raise ValueError('blocked task graph')
                break
            now=next_arrival;continue
        step=min(safe_at[name]-now for name in running if name is not None)
        if next_arrival is not None and next_arrival>now:step=min(step,next_arrival-now)
        for name in running:
            if name is not None:left[name]-=step;work_spent[name]+=step
        now+=step
    # Publish validity is checked at completion's generation, not the final
    # generation: feedback may have been current before a subsequent edit.
    latest_at={}
    for event,at,name in events:
        task=byname[name]
        if event=='arrival' and not task.durable:latest_at[task.client]=max(latest_at.get(task.client,0),task.generation)
        if event=='finish' and name in published:assert task.durable or task.generation==latest_at[task.client]
    assert all(status[t.name]=='done' for t in tasks if t.durable)
    assert all(status[t.name]=='done' for t in tasks if not t.durable and t.generation==latest[t.client])
    current=[t for t in tasks if not t.durable and t.generation==latest[t.client]]
    latency=[finished[t.name]-t.arrival for t in current]
    return dict(policy=policy,cancellation=cancellation,makespan_model_units=now,executed_work_model_units=sum(work_spent.values()),
                obsolete_work_model_units=sum(work_spent[n] for n in status if status[n]=='cancelled' or (status[n]=='done' and n not in published)),
                cold_setup_model_units=cold_work,current_final_latency_max=max(latency),current_final_latency_mean=statistics.mean(latency),
                max_queue_delay_by_client={c:max(w for client,w in queue_wait if client==c) for c in {c for c,_ in queue_wait}},
                published=len(published),cancelled=sum(v=='cancelled' for v in status.values()),decisions=decisions,
                decision_cpu_observation_ns=overhead,events=events,status=status)
