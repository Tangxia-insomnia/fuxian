"""E10-specific checks; read saved solver results, no solver.check in tests."""
from pathlib import Path
import copy, hashlib, json, sys, unittest
from unittest import mock
import z3
import caller_path_smt as scalar
ROOT=Path(__file__).resolve().parent
CASES=[(304,False,0,None),(944,False,0,None),(999,False,0,None),(999999,False,999,None),(1000000,True,1000,100),(45000000,True,45000,2),(45000001,False,45000,None),(0,False,None,None)]
class CallerPathChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=scalar.load_materials();cls.results=scalar.load(ROOT/'experiment_results.json')
    def test_01_original_identity_and_three_hashes(self):
        v=scalar.load(ROOT/'input_verification.json')
        self.assertEqual({v[k] for k in ['formal_body_sha256','original_JSON_computed_UTF8_body_sha256','E09_contract_source_body_sha256','E09_results_source_body_sha256']},{scalar.BODY_SHA256})
        self.assertEqual((self.m['source_record']['index'],self.m['source_record']['result']),(4,0))
        self.assertEqual(self.m['source_record']['function_call'][0],v['function_body'])
    def test_02_pinned_source_and_callsite_coordinates(self):
        verified=scalar.load(ROOT/'upstream_body_verification.json')
        self.assertEqual((verified['function_start_line'],verified['alert_line']),(107,110))
        self.assertEqual(verified['status'],'EXACT_BYTE_MATCH')
        self.assertEqual(self.m['manifest']['commit'],scalar.COMMIT)
        self.assertEqual(len(self.m['manifest']['sources']),29)
        self.assertEqual(len(self.m['evidence']['facts']),53)
        self.assertFalse(self.m['manifest']['generic_AST_proof_claimed'])
    def test_03_macro_closed_unsigned_interval(self):
        lo,hi=1000000,45000000
        for value in [0,304,944,999,999999,lo,lo+1,hi-1,hi,hi+1,(1<<31)-1,1<<31,(1<<32)-1]:
            macro=(lo<=value<=hi) or (hi<=value<=lo)
            self.assertEqual(macro,lo<=value<=hi)
            x=z3.BitVecVal(value,32)
            self.assertEqual(z3.is_true(z3.simplify(z3.And(z3.UGE(x,z3.BitVecVal(lo,32)),z3.ULE(x,z3.BitVecVal(hi,32))))),macro)
        self.assertTrue(self.m['contract']['range']['closed'])
        self.assertFalse(self.m['contract']['range']['human_added_numeric_assumption'])
    def test_04_five_callback_configurations(self):
        configs=self.m['evidence']['configurations']
        self.assertEqual(len(configs),5)
        self.assertEqual([c['tuner_family'] for c in configs].count('STB6100'),4)
        self.assertEqual([c['tuner_family'] for c in configs].count('TDA8261'),1)
        for cfg in configs:
            self.assertEqual(cfg['callbacks']['tuner_set_rfsiggain'],'NULL')
            self.assertEqual(scalar.scope_status(self.m['review'],cfg['configuration_id']),'SCOPED_SOURCE_REVIEW_ADMITTED')
    def test_05_no_transfer_across_unknown_effect(self):
        changed=dict(self.m);changed['review']=copy.deepcopy(self.m['review'])
        changed['review']['unresolved_modification_paths_within_declared_scope'].append({'callback':'unreviewed'})
        with mock.patch.object(z3,'SolverFor') as solver:
            self.assertEqual(scalar.scope_status(changed['review']),'UNKNOWN')
            with self.assertRaises(scalar.EvidenceUnknown):scalar.encode(changed,32)
            solver.assert_not_called()
    def test_06_out_of_tree_and_unverified_sync_are_unknown(self):
        with mock.patch.object(z3,'SolverFor') as solver:
            for width in (32,64):
                with self.assertRaises(scalar.EvidenceUnknown):scalar.encode(self.m,width,configuration_id='out-of-tree')
            changed=dict(self.m);changed['review']=copy.deepcopy(self.m['review']);changed['review']['reviews'][-1]['result']='UNKNOWN'
            with self.assertRaises(scalar.EvidenceUnknown):scalar.encode(changed,64)
            solver.assert_not_called()
    def test_07_other_delivery_branch_has_no_target_call(self):
        for width in (32,64):
            for delivery in ('SYS_DVBS','SYS_DSS'):
                self.assertTrue(scalar.reference_path(self.m,1000000,width,delivery)['target_call_reached'])
            self.assertFalse(scalar.reference_path(self.m,1000000,width,'SYS_DVBS2')['target_call_reached'])
            with self.assertRaises(scalar.EvidenceUnknown):scalar.encode(self.m,width,delivery_system='SYS_DVBS2')
    def test_08_requested_boundaries_both_widths(self):
        for width in (32,64):
            for value,accepted,inner,result in CASES:
                with self.subTest(width=width,srate=value):
                    ref=scalar.reference_path(self.m,value,width)
                    self.assertEqual(ref['caller_range_passed'],accepted)
                    self.assertEqual(ref['target_call_reached'],accepted)
                    self.assertEqual(ref['counterfactual_local_result']['inner'],inner)
                    if accepted:
                        self.assertEqual(ref['actual_target_result']['return_value'],result)
                        self.assertFalse(ref['actual_target_result']['outer_denominator_zero'])
                    else:self.assertIsNone(ref['actual_target_result'])
    def test_09_formula_concrete_differential(self):
        for width in (32,64):
            enc=scalar.encode(self.m,width)
            for value in [0,304,944,999,999999,1000000,1000001,44999999,45000000,45000001,(1<<31)-1,1<<31,(1<<32)-1]:
                pairs=[(v,z3.BitVecVal(value,32)) for v in enc['u32_variables'].values()]+[(enc['signed_long'],z3.BitVecVal(value,width)),(enc['selected_delivery'],z3.BoolVal(True))]
                eligible=1000000<=value<=45000000
                prefix=z3.simplify(z3.substitute(z3.And(*enc['constraints']),*pairs))
                self.assertEqual(z3.is_true(prefix),eligible)
                fault=z3.simplify(z3.substitute(z3.And(*enc['constraints'],enc['fault']),*pairs))
                self.assertTrue(z3.is_false(fault))
                if 0<value<=(1<<(width-1))-1:
                    quotient=z3.simplify(z3.substitute(enc['inner'],*pairs)).as_signed_long()
                    self.assertEqual(quotient,self.m['helper'].c_signed_divide(value,1000,width))
    def test_10_field_copy_is_not_reused_after_a_write(self):
        for width in (32,64):
            enc=scalar.encode(self.m,width)
            pairs=[(v,z3.BitVecVal(944 if name=='target_params_srate' else 1000000,32)) for name,v in enc['u32_variables'].items()]+[(enc['signed_long'],z3.BitVecVal(944,width)),(enc['selected_delivery'],z3.BoolVal(True))]
            self.assertTrue(z3.is_false(z3.simplify(z3.substitute(z3.And(*enc['constraints']),*pairs))))
    def test_11_conversions_and_unsupported_inputs(self):
        for width in (16,128,True,'32',None):
            with self.assertRaises(scalar.UnsupportedSemantics):scalar.encode(self.m,width)
        for args in [{'input_type':'signed long'},{'input_type':'pointer'},{'division':'floor'}]:
            with self.assertRaises(scalar.UnsupportedSemantics):scalar.encode(self.m,32,**args)
        for value in (-1,1<<32,True,1.5):
            with self.assertRaises(scalar.UnsupportedSemantics):scalar.reference_path(self.m,value,32)
        with self.assertRaises(scalar.UnsupportedSemantics):scalar.u32_to_long_reference(1<<31,32)
        self.assertEqual(scalar.u32_to_long_reference((1<<32)-1,64),(1<<32)-1)
        self.assertIn('zero_extend 32',scalar.encode(self.m,64)['relationships'][4][1].sexpr())
    def test_12_division_definedness_and_independent_bounds(self):
        for width in (32,64):
            h=self.m['helper'];v=lambda n:z3.BitVecVal(n,width)
            self.assertEqual(h.c_signed_divide(-1001,1000,width),-1)
            self.assertEqual(h.c_signed_divide(-999,1000,width),0)
            for a,b in [(1,0),(-(1<<(width-1)),-1)]:
                with self.assertRaises(h.CUndefinedBehavior):h.c_signed_divide(a,b,width)
                _,defined=h.signed_division(v(a),v(b),width)
                self.assertTrue(z3.is_false(z3.simplify(defined)))
            math=scalar.independent_interval_check(self.m,width)
            self.assertEqual(math['status'],'MATCH_NONZERO_DENOMINATOR')
            self.assertEqual(math['inner_quotient_interval'],[1000,45000])
            self.assertEqual(math['outer_return_interval'],[2,100])
            self.assertFalse(math['z3_used'])
    def test_13_saved_queries_and_no_alert_authority(self):
        self.assertEqual(self.results['solver_check_calls'],2)
        self.assertEqual({(r['width_bits'],r['status']) for r in self.results['runs']},{(32,'UNSAT'),(64,'UNSAT')})
        self.assertTrue(self.results['both_contracts_agree'])
        self.assertEqual(self.results['implementation_sha256'],scalar.sha((ROOT/'caller_path_smt.py').read_bytes()))
        for run in self.results['runs']:
            self.assertEqual(run['formula_smt2'],(ROOT/run['formula_file']).read_text(encoding='utf-8'))
            for operator in ('bvsdiv','bvuge','bvule'):self.assertIn(operator,run['formula_smt2'])
            self.assertFalse(run['outer_definedness_asserted_in_fault_query'])
            self.assertFalse(run['filter_authority']);self.assertIsNone(run['original_alert_decision'])
            self.assertEqual(run['full_program_semantics'],'UNKNOWN')
            self.assertIsNone(run['model'])
            self.assertFalse(run['unsat_proof']['certificate_independently_checked'])
    def test_14_E09_SAT_preserved_as_local_only(self):
        control=self.results['E09_control_reference']
        self.assertFalse(control['rerun']);self.assertTrue(control['B_remains_human_hypothesis_not_used'])
        self.assertEqual({(r['width'],r['status']) for r in control['local_A']},{(32,'SAT'),(64,'SAT')})
        for item in control['local_A']:
            value=item['model']['srate_signed']
            ref=scalar.reference_path(self.m,value,item['width'])
            self.assertFalse(ref['target_call_reached']);self.assertTrue(ref['counterfactual_local_result']['outer_denominator_zero'])
    def test_15_changed_frozen_contract_stops_before_solver(self):
        target=ROOT/'caller_path_contract.json';original=Path.read_bytes
        def changed_bytes(path):return original(path)+b' ' if path==target else original(path)
        with mock.patch.object(Path,'read_bytes',autospec=True,side_effect=changed_bytes),mock.patch.object(z3,'SolverFor') as solver:
            with self.assertRaises(scalar.IntegrityError):scalar.load_materials()
            solver.assert_not_called()
if __name__=='__main__':
    if (ROOT/'test_results.json').exists():raise FileExistsError('Test record exists; no overwrite or automatic rerun')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CallerPathChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    materials=CallerPathChecks.m
    observations=[scalar.reference_path(materials,value,width) for width in (32,64) for value,_,_,_ in CASES]
    doc={'phase':'E10','attempt':2,'status':'PASS' if result.wasSuccessful() else 'FAIL','test_methods':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'failure_details':[{'test':str(test),'traceback':detail} for test,detail in result.failures+result.errors],'required_boundary_observations':observations,'boundary_observation_count':len(observations),'finite_formula_substitution_inputs_per_width':13,'finite_formula_substitution_cases':26,'concrete_substitutions_are_not_solver_checks':True,'tests_additional_solver_check_calls':scalar.CHECK_COUNT,'native_kernel_or_C_execution_count':0,'reference_scope':'Abstract scalar path eligibility and counterfactual local arithmetic; no actual frontend or hardware execution','experiments_sha256':scalar.sha((ROOT/'experiment_results.json').read_bytes()),'test_implementation_sha256':scalar.sha(Path(__file__).read_bytes()),'original_alert_decision':None,'filter_authority':False,'full_program_semantics':'UNKNOWN'}
    scalar.write_new(ROOT/'test_results.json',doc)
    print(json.dumps({'status':doc['status'],'test_methods':doc['test_methods'],'boundary_observations':len(observations),'additional_solver_checks':scalar.CHECK_COUNT}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
