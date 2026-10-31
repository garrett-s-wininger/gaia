"""Sequential pebble model: all dependency pebbles and scratch must fit."""
from dataclasses import dataclass
from functools import lru_cache
import heapq
import itertools


@dataclass(frozen=True)
class Node:
    size: int
    cost: int
    scratch: int
    deps: tuple[str, ...] = ()


def necessary(nodes, roots):
    result = set()
    active = set()
    def visit(name):
        if name in active:raise ValueError('pebble model requires DAG')
        if name in result:
            return
        node=nodes[name]
        if node.size<=0 or node.cost<0 or node.scratch<0:raise ValueError('invalid node costs')
        active.add(name)
        for dep in nodes[name].deps:
            visit(dep)
        active.remove(name);result.add(name)
    for root in roots:
        visit(root)
    return result


def simulate(nodes, requests, budget, policy):
    necessary(nodes, requests)
    cache = set()
    access = {}
    pins = {}
    clock = 0
    cost = 0
    recomputations = 0
    evictions = 0
    peak = 0
    counts = {}
    def used():return sum(nodes[n].size for n in cache)
    def ensure(amount):
        nonlocal evictions
        while used() + amount > budget:
            candidates = cache - {n for n,count in pins.items() if count}
            if not candidates or policy == 'retain-all':
                raise ValueError('infeasible admitted live set')
            if policy == 'lru':
                victim = min(candidates, key=lambda n:(access.get(n, -1), n))
            elif policy == 'cost-size':
                victim = min(candidates, key=lambda n:(nodes[n].cost / nodes[n].size, access.get(n, -1), n))
            else:raise ValueError(policy)
            cache.remove(victim);evictions += 1
    def compute(name):
        nonlocal cost, clock, peak, recomputations
        if name in cache:
            pins[name]=pins.get(name,0)+1;clock += 1;access[name] = clock;return
        node = nodes[name]
        for dep in node.deps:
            compute(dep)
        ensure(node.size + node.scratch)
        peak = max(peak, used() + node.size + node.scratch)
        cost += node.cost
        if counts.get(name, 0):recomputations += 1
        counts[name] = counts.get(name, 0) + 1
        cache.add(name);pins[name]=pins.get(name,0)+1;clock += 1;access[name] = clock
        for dep in node.deps:
            pins[dep]-=1
    try:
        for root in requests:
            compute(root);pins[root]-=1
    except ValueError as error:
        return dict(status='infeasible',error=str(error),cost=cost,peak_bytes=peak,evictions=evictions,recomputations=recomputations)
    return dict(status='complete',cost=cost,peak_bytes=peak,evictions=evictions,recomputations=recomputations,computations=sum(counts.values()),retained_bytes=used())


def optimal(nodes, requests, budget):
    """Exact Dijkstra oracle over tiny sequential pebble states, with foresight."""
    names=tuple(sorted(necessary(nodes,requests)))
    if len(names)>12:
        raise ValueError('offline oracle bounded to12nodes')
    serial=itertools.count();initial=(0,frozenset());queue=[(0,next(serial),initial)];distance={initial:0};expanded=0
    while queue:
        cost,_,(index,cache)=heapq.heappop(queue)
        if distance[(index,cache)]!=cost:continue
        expanded+=1
        if index==len(requests):return dict(status='complete',cost=cost,expanded_states=expanded)
        successors=[]
        if requests[index] in cache:successors.append(((index+1,cache),0))
        for victim in cache:successors.append(((index,cache-{victim}),0))
        used=sum(nodes[n].size for n in cache)
        for name in names:
            node=nodes[name]
            if name not in cache and set(node.deps)<=cache and used+node.size+node.scratch<=budget:
                successors.append(((index,cache|{name}),node.cost))
        for state,extra in successors:
            candidate=cost+extra
            if candidate<distance.get(state,float('inf')):
                distance[state]=candidate;heapq.heappush(queue,(candidate,next(serial),state))
    return dict(status='infeasible',expanded_states=expanded)


def fixture():
    return {'source':Node(2,2,0),'parse':Node(3,20,1,('source',)),
            'facts':Node(2,8,1,('parse',)),'code':Node(3,30,1,('parse',)),
            'lint':Node(1,5,0,('facts',)),'binary':Node(2,15,1,('code',))}
