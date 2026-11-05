from types import SimpleNamespace
from unittest.mock import Mock

from app.services.fiscal_uuid_lock import lock_fiscal_uuid


def test_postgres_uuid_claim_lock_is_stable_and_scoped_to_the_uuid():
    db = Mock()
    db.get_bind.return_value.dialect.name = "postgresql"
    uuid = "12345678-ABCD-1234-ABCD-1234567890AB"
    lock_fiscal_uuid(db, uuid)
    lock_fiscal_uuid(db, uuid.lower())
    lock_fiscal_uuid(db, "99999999-ABCD-1234-ABCD-1234567890AB")
    params = [next(iter(call.args[0].compile().params.values())) for call in db.execute.call_args_list]
    assert params[0] == params[1] and params[0] != params[2]
    assert "pg_advisory_xact_lock" in str(db.execute.call_args.args[0])


def test_sqlite_does_not_call_postgres_functions():
    db = Mock()
    db.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    lock_fiscal_uuid(db, "12345678-ABCD-1234-ABCD-1234567890AB")
    db.execute.assert_not_called()
