import copy,json,tempfile,unittest
from pathlib import Path
from jsonschema import Draft7Validator,ValidationError

ROOT=Path(__file__).resolve().parents[1]
FIXED_TIME="2026-07-10T00:00:00Z"
from tools.ci_upgrade_engine import build_upgrade_report,compute_upgrade_sha256
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE,MINIMAL_SAFE_CI


def load_json(path:Path):return json.loads(path.read_text(encoding="utf-8"))
def materialize(root:Path):
    (root/"pyproject.toml").write_text("[project]\nname='schema-test'\nversion='0.1.0'\n[build-system]\nbuild-backend='setuptools.build_meta'\n",encoding="utf-8");(root/"tests").mkdir();(root/"tests/test_sample.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_invalid(self):\n  with self.assertRaises(ValueError): raise ValueError('invalid')\n",encoding="utf-8")

class RepositoryUpgradeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.legacy_schema=load_json(ROOT/"schemas/repository_upgrade_report.v1.schema.json")
        self.report_schema=load_json(ROOT/"schemas/repository_upgrade_report.v1.1.schema.json")
        self.profile_schema=load_json(ROOT/"schemas/capability_profiles.v1.schema.json")
        for schema in (self.legacy_schema,self.report_schema,self.profile_schema):Draft7Validator.check_schema(schema)

    def test_profile_catalog_validates(self):Draft7Validator(self.profile_schema).validate(load_json(ROOT/"profiles/capability-profiles.v1.json"))

    def test_legacy_static_examples_remain_valid_and_hash_match(self):
        for name in ("repository_upgrade_report.minimal.example.json","repository_upgrade_report.deep.example.json"):
            with self.subTest(name=name):
                instance=load_json(ROOT/"examples"/name);Draft7Validator(self.legacy_schema).validate(instance);self.assertEqual(instance["evidence_sha256"],compute_upgrade_sha256(instance))

    def test_generated_v1_1_minimal_and_deep_reports_validate(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td);materialize(repo)
            for mode in (MINIMAL_SAFE_CI,DEEP_REPOSITORY_UPGRADE):
                with self.subTest(mode=mode):Draft7Validator(self.report_schema).validate(build_upgrade_report(repo,mode=mode,generated_at=FIXED_TIME))

    def test_minimal_report_rejects_deep_only_fields(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td);materialize(repo);report=build_upgrade_report(repo,mode=MINIMAL_SAFE_CI,generated_at=FIXED_TIME);report["deep_audit"]={}
            with self.assertRaises(ValidationError):Draft7Validator(self.report_schema).validate(report)

    def test_deep_report_requires_staged_upgrade_and_implementation_package(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td);materialize(repo);report=build_upgrade_report(repo,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME)
            for field in ("staged_upgrade","implementation_package"):
                broken=copy.deepcopy(report);broken.pop(field)
                with self.subTest(field=field),self.assertRaises(ValidationError):Draft7Validator(self.report_schema).validate(broken)

    def test_schema_rejects_unknown_capability_state(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td);materialize(repo);report=build_upgrade_report(repo,mode=DEEP_REPOSITORY_UPGRADE,generated_at=FIXED_TIME);report["repository_model"]["capabilities"][0]["state"]="maybe"
            with self.assertRaises(ValidationError):Draft7Validator(self.report_schema).validate(report)

    def test_profile_schema_rejects_unknown_fields(self):
        invalid=copy.deepcopy(load_json(ROOT/"profiles/capability-profiles.v1.json"));invalid["profiles"][0]["unexpected"]=True
        with self.assertRaises(ValidationError):Draft7Validator(self.profile_schema).validate(invalid)

if __name__=="__main__":unittest.main()
