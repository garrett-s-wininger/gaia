import itertools
import random
import unittest
from patches import Entry, Edit, apply, inverse, compose, commute, join_facts, alternatives, Target
from facts import Spec, Engine, Frontier, Relational, full_oracle
import retention
import scheduling


ENTRIES=(None,Entry('file',b'a'),Entry('file',b'b'),Entry('file',b'a',True),Entry('link',b'target'))


class PatchTests(unittest.TestCase):
    def test_exhaustive_context_composition_inverse_and_commute(self):
        for a,b in itertools.product(ENTRIES,repeat=2):
            state={k:v for k,v in [('a',a),('b',b)] if v is not None}
            for av,bv in itertools.product(ENTRIES,repeat=2):
                p=(Edit('a',a,av),);q=(Edit('b',b,bv),)
                expected={k:v for k,v in [('a',av),('b',bv)] if v is not None}
                self.assertEqual(apply(state,compose(p,q)),expected)
                self.assertEqual(apply(apply(state,p),inverse(p)),state)
                swap=commute(p,q);self.assertIsNotNone(swap)
                self.assertEqual(apply(state,compose(*swap)),expected)

    def test_partial_domain_and_atomic_failure(self):
        state={'a':Entry('file',b'a')}
        with self.assertRaises(ValueError):apply(state,(Edit('a',None,Entry('file',b'b')),))
        with self.assertRaises(ValueError):apply(state,(Edit('a/b',None,Entry('file',b'b')),))
        self.assertEqual(state,{'a':Entry('file',b'a')})
        self.assertIsNone(commute((Edit('a',None,None),),(Edit('a/b',None,None),)))

    def test_lattice_and_authority_are_distinct(self):
        values=[frozenset(),frozenset({(1,'answer','left')}),frozenset({(1,'answer','right')})]
        for a,b,c in itertools.product(values,repeat=3):
            self.assertEqual(join_facts(a,b),join_facts(b,a))
            self.assertEqual(join_facts(join_facts(a,b),c),join_facts(a,join_facts(b,c)))
            self.assertEqual(join_facts(a,a),a)
        both=join_facts(values[1],values[2]);self.assertEqual(alternatives(both,1,'answer'),frozenset({'left','right'}))
        target=Target();self.assertTrue(target.publish(0,'left'));self.assertFalse(target.publish(0,'right'));self.assertEqual(target.head,'left')


class FactTests(unittest.TestCase):
    def fixture(self):
        specs={'a':Spec((('early/x','late/x'),),deps=('b',)), 'b':Spec((('optional',),),deps=('a',)),
               'test:one':Spec(deps=('a',)), 'editor:one':Spec(directories=('early',),env_lookup='PICK')}
        files={'late/x':b'base','default/selected.h':b'config'}
        return specs,files,{}

    def test_negative_shadowing_removal_cycles_environment_and_membership(self):
        specs,files,env=self.fixture();engines=[c(specs,files,env) for c in (Engine,Frontier,Relational)]
        changes=[dict(files={'early/x':b'shadow'}),dict(files={'optional':b'appeared'}),dict(files={'early/x':None}),
                 dict(env={'PICK':'other'}),dict(files={'other/selected.h':b'config2'}),dict(files={'early/new':b'member'}),
                 dict(specs={'a':Spec((('early/x','late/x'),),deps=())}),dict(files={'optional':None})]
        for change in changes:
            results=[e.update(**change) for e in engines]
            for e in engines:self.assertEqual(e.outputs,full_oracle(e.specs,e.files,e.env))
            self.assertEqual(results[0]['selected_tests'],results[1]['selected_tests']);self.assertEqual(results[0]['changed_outputs'],results[2]['changed_outputs'])

    def test_unobserved_later_candidate_does_not_invalidate(self):
        specs={'test:a':Spec((('first','second'),))};files={'first':b'one','second':b'two'}
        for cls in (Frontier,Relational):
            engine=cls(specs,files,{});result=engine.update(files={'second':b'changed'})
            self.assertEqual(result['evaluated_nodes'],0);self.assertFalse(result['selected_tests'])

    def test_random_edits_against_independent_closure_oracle(self):
        rng=random.Random(812);specs={f'n{i}':Spec(((f'f{i}',),),deps=tuple(f'n{j}' for j in range(12) if rng.random()<.08)) for i in range(12)}
        files={f'f{i}':str(i).encode() for i in range(12)};engines=[c(specs,files,{}) for c in (Engine,Frontier,Relational)]
        for step in range(50):
            index=rng.randrange(12);change={f'f{index}':None if step%3==0 else str(step).encode()}
            rows=[e.update(files=change) for e in engines]
            self.assertEqual(engines[0].outputs,engines[1].outputs);self.assertEqual(engines[0].outputs,engines[2].outputs)
            self.assertEqual(rows[0]['changed_outputs'],rows[1]['changed_outputs']);self.assertEqual(rows[0]['changed_outputs'],rows[2]['changed_outputs'])


class RetentionTests(unittest.TestCase):
    def test_heuristics_cannot_beat_offline_oracle(self):
        nodes=retention.fixture();requests=['lint','binary','lint','binary','lint']
        for budget in (7,9,12,20):
            oracle=retention.optimal(nodes,requests,budget)
            for policy in ('retain-all','lru','cost-size'):
                result=retention.simulate(nodes,requests,budget,policy)
                self.assertLessEqual(result['peak_bytes'],budget)
                if result['status']=='complete':
                    self.assertEqual(oracle['status'],'complete');self.assertGreaterEqual(result['cost'],oracle['cost'])

    def test_nested_lease_counts_and_cycles(self):
        n=retention.Node;nodes={'a':n(2,1,0),'b':n(2,1,0,('a',)),'c':n(2,1,0,('a','b'))}
        self.assertEqual(retention.simulate(nodes,['c'],6,'lru')['status'],'complete')
        nodes={'a':n(1,1,0,('b',)),'b':n(1,1,0,('a',))}
        with self.assertRaises(ValueError):retention.simulate(nodes,['a'],10,'lru')


class SchedulingTests(unittest.TestCase):
    def test_policies_publish_current_work_and_preserve_durable_tasks(self):
        for policy in ('fifo','critical','fair','work-stealing','foraging'):
            row=scheduling.simulate(scheduling.fixture(generations=5),policy)
            self.assertTrue(all(v=='done' for n,v in row['status'].items() if n.startswith('bulk:')))
            self.assertGreater(row['published'],0)

    def test_no_cancellation_control_and_cyclic_rejection(self):
        tasks=scheduling.fixture(generations=3)
        uncancelled=scheduling.simulate(tasks,'fifo',cancellation=False)
        self.assertFalse(uncancelled['cancelled'])
        t=scheduling.Task
        with self.assertRaises(ValueError):scheduling.simulate([t('a','x',1,0,1,'g',('b',)),t('b','x',1,0,1,'g',('a',))],'fifo')

    def test_new_arrival_does_not_create_a_safe_cancellation_point(self):
        t=scheduling.Task
        tasks=[t('old','client',1,0,10,'g'),t('new','client',2,3,1,'g')]
        row=scheduling.simulate(tasks,'fifo',workers=1,quantum=4,cold_cost=0)
        self.assertIn(('cancel-running',4,'old'),row['events'])
        self.assertNotIn(('cancel-running',3,'old'),row['events'])


if __name__=='__main__':unittest.main()
