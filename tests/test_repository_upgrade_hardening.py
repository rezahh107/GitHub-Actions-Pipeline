import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from jsonschema import Draft7Validator,ValidationError

ROOT=Path(__file__).resolve().parents[1]
FIXED_TIME="2026-07-10T00:00:00Z"
from tools.ci_implementation_engine import apply_implementation_package
from tools.ci_outcome_registry import build_profile_evolution_proposals
from tools.ci_profiles import compose_profile_contributions,detect_profiles
from tools.ci_repository_model import build_repository_model
from tools.ci_upgrade_engine import build_upgrade_report
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE,MINIMAL_SAFE_CI,UpgradeContractError


def write_files(root,files):
    for rel,content in files.items():
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding="utf-8")

def init_git(root):
    subprocess.run(["git","init","-q"],cwd=root,check=True);subprocess.run(["git","config","user.email","test@example.test"],cwd=root,check=True);subprocess.run(["git","config","user.name","Test"],cwd=root,check=True);subprocess.run(["git","add","."],cwd=root,check=True);subprocess.run(["git","commit","-q","-m","initial"],cwd=root,check=True);return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()

class HardeningTests(unittest.TestCase):
    def test_semantic_model_resolves_test_import_entry_and_route(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"pyproject.toml":"[project]\nname='api'\nversion='0.1.0'\ndependencies=['fastapi']\n[project.scripts]\nserve='app.api:main'\n","app/api.py":"from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef health(): return {'ok':True}\ndef main(): return 0\n","tests/test_api.py":"from app.api import health\ndef test_health(): assert health()['ok']\n"})
            model=build_repository_model(root)
            self.assertTrue(any(x.get("signal_type")=="python_route" for x in model["semantic_model"]["signals"]))
            self.assertTrue(any(x.get("relationship_type")=="source_to_test" and x.get("resolution_state")=="resolved" for x in model["relationships"]))
            self.assertTrue(any(x.get("signal_type")=="declared_entry_point" and x.get("resolution_state")=="resolved" for x in model["semantic_model"]["signals"]))

    def test_workspace_boundaries_come_from_declaration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"package.json":json.dumps({"name":"root","workspaces":["packages/*"]}),"packages/a/package.json":json.dumps({"name":"a","scripts":{"test":"node test.js"}}),"packages/a/test.js":"console.log('ok')\n"})
            model=build_repository_model(root)
            component=next(x for x in model["components"] if x["root"]=="packages/a")
            self.assertEqual(component["boundary_basis"],"workspace_declared")

    def test_profile_detection_preserves_signals_and_conflicts(self):
        model={"languages":["Python"],"frameworks":[],"repository_archetypes":[],"manifests":[],"entry_points":[],"semantic_model":{"signals":[]},"lockfiles":[],"config_files":[],"validators":[],"schemas":[],"examples":[],"generated_artifacts":[],"release_paths":[],"workflows":[]}
        catalog={"profile_contract_version":"1.0.0","profiles":[{"profile_id":"expects","category":"x","detect":{"languages_any":["Python"]},"expected_capabilities":["build_verified"],"exclusions":[],"structural_invariants":[],"common_failure_modes":[],"candidate_checks":[],"cost_noise":"x"},{"profile_id":"excludes","category":"x","detect":{"languages_any":["Python"]},"expected_capabilities":[],"exclusions":["build_verified"],"structural_invariants":[],"common_failure_modes":[],"candidate_checks":[],"cost_noise":"x"}]}
        matches=detect_profiles(model,catalog);self.assertTrue(all(x["matched_signals"] for x in matches));composition=compose_profile_contributions(matches,catalog);self.assertEqual(composition["profile_conflicts"][0]["capability_id"],"build_verified");self.assertNotIn("build_verified",composition["expected_capabilities"])

    def test_ranking_contains_policy_inputs_and_factor_rationale(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"pyproject.toml":"[project]\nname='x'\nversion='0.1'\n[build-system]\nbuild-backend='setuptools.build_meta'\n","tests/test_x.py":"import unittest\nclass T(unittest.TestCase): pass\n"})
            report=build_upgrade_report(root,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME)
            item=report["recommendations"]["ranked"][0];self.assertEqual(item["ranking"]["model_version"],"1.1.0");self.assertEqual(set(item["ranking"]["factor_rationale"]),set(item["ranking"]["factors"]));self.assertIn("capability_state",item["ranking"]["inputs"])

    @unittest.skipUnless(shutil.which("git"),"git required")
    def test_implementation_engine_requires_exact_clean_head_and_applies_allowlisted_recipe(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"pyproject.toml":"[project]\nname='cli'\nversion='0.1'\n[project.scripts]\ncli='app.cli:main'\n","app/cli.py":"def main(): return 0\n","tests/test_cli.py":"import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"});head=init_git(root)
            report=build_upgrade_report(root,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME);package=report["implementation_package"];action=next(x for x in package["actions"] if x["recipe_id"]=="add-python-pr-test-workflow-v1");self.assertEqual(action["status"],"applicable")
            result=apply_implementation_package(root,package,allowed_recipe_ids={"add-python-pr-test-workflow-v1"},expected_head_sha=head)
            self.assertEqual(result["results"][0]["status"],"applied");self.assertFalse(result["repository_commands_executed"]);self.assertTrue((root/".github/workflows/repository-upgrade-tests.yml").is_file())

    @unittest.skipUnless(shutil.which("git"),"git required")
    def test_implementation_engine_rejects_head_mismatch_and_dirty_worktree(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"pyproject.toml":"[project]\nname='x'\nversion='0.1'\n","tests/test_x.py":"import unittest\n"});head=init_git(root);report=build_upgrade_report(root,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME)
            with self.assertRaises(UpgradeContractError) as ctx:apply_implementation_package(root,report["implementation_package"],allowed_recipe_ids={"add-python-pr-test-workflow-v1"},expected_head_sha="0"*40)
            self.assertEqual(ctx.exception.code,"IMPLEMENTATION_HEAD_MISMATCH")
            (root/"dirty.txt").write_text("x",encoding="utf-8")
            with self.assertRaises(UpgradeContractError) as ctx:apply_implementation_package(root,report["implementation_package"],allowed_recipe_ids={"add-python-pr-test-workflow-v1"},expected_head_sha=head)
            self.assertEqual(ctx.exception.code,"IMPLEMENTATION_WORKTREE_DIRTY")

    def test_profile_evolution_is_thresholded_review_only_and_deterministic(self):
        outcomes=[]
        for i in range(3):outcomes.append({"outcome_id":f"o{i}","repository_fingerprint":hashlib.sha256(f"r{i}".encode()).hexdigest(),"profile_ids":["python-cli"],"recommendation_id":"INV-TESTS-EXECUTED-ON-PR","capability_id":"tests_run_on_pull_requests","pre_capability_state":"absent","implementation_status":"applied","post_capability_state":"operational","validation":{"exact_head_sha":str(i)*40,"workflow_conclusion":"success"}})
        registry={"outcome_contract_version":"1.0.0","outcomes":outcomes};first=build_profile_evolution_proposals(registry);second=build_profile_evolution_proposals(registry);self.assertEqual(first,second);self.assertFalse(first["automatic_registry_mutation"]);self.assertEqual(len(first["proposals"]),1);self.assertEqual(first["proposals"][0]["status"],"proposed_for_human_review")

    def test_deep_report_has_implementation_package_minimal_does_not(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"README.md":"x\n"});deep=build_upgrade_report(root,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME);minimal=build_upgrade_report(root,mode=MINIMAL_SAFE_CI,generated_at=FIXED_TIME);self.assertIn("implementation_package",deep);self.assertNotIn("implementation_package",minimal)

    def test_new_registries_and_report_validate(self):
        for schema_name,data_path in (("ranking_policy.v1.schema.json","profiles/ranking-policy.v1.json"),("implementation_recipes.v1.schema.json","profiles/implementation-recipes.v1.json")):
            schema=json.loads((ROOT/"schemas"/schema_name).read_text());Draft7Validator.check_schema(schema);Draft7Validator(schema).validate(json.loads((ROOT/data_path).read_text()))
        report_schema=json.loads((ROOT/"schemas/repository_upgrade_report.v1.1.schema.json").read_text());Draft7Validator.check_schema(report_schema)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_files(root,{"README.md":"x\n"});Draft7Validator(report_schema).validate(build_upgrade_report(root,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME))

if __name__=="__main__":unittest.main()
