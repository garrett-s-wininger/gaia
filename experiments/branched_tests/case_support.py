"""Explicit fixture extensions and request assertions, shared by all modes."""
import datetime
import hashlib
import json
import os
from pathlib import Path


def extend_fixture():
    from django.core.files.base import ContentFile
    from todo.models import Attachment, Task
    task = Task.objects.order_by("id").first()
    attachment = Attachment(task=task, added_by=task.created_by)
    attachment.file.save("prepared.txt", ContentFile(b"prepared attachment\n"), save=True)


def verify_fixture():
    from django.conf import settings
    from todo.models import Attachment, Task, TaskList
    from django.contrib.auth import get_user_model
    assert Task.objects.count() == 6
    assert sorted(Task.objects.values_list("title", flat=True)) == ["Task 1", "Task 1", "Task 2", "Task 2", "Task 3", "Task 3"]
    assert TaskList.objects.count() == 2
    assert get_user_model().objects.count() == 3
    attachment = Attachment.objects.get()
    assert Path(attachment.file.path).read_bytes() == b"prepared attachment\n"
    assert Path(attachment.file.path).resolve().is_relative_to(Path(settings.MEDIA_ROOT).resolve())
    assert not (Path(settings.MEDIA_ROOT) / "leaked.txt").exists()
    import todo.models
    assert not hasattr(todo.models, "_gaia_leaked_heap")
    task = Task.objects.first(); task.due_date = datetime.date.today()
    overdue = bool(task.overdue_status())
    assert overdue == (os.environ["GAIA_REVISION"] == "inclusive")
    from todo.utils import staff_check
    user = get_user_model().objects.get(username="u1"); user.is_staff = False
    permitted = bool(staff_check(user))
    assert permitted == (os.environ["GAIA_STAFF_ONLY"] != "1")
    return {"tasks": 6, "lists": 2, "users": 3, "attachment": hashlib.sha256(b"prepared attachment\n").hexdigest(),
            "overdue_today": overdue, "nonstaff_permitted": permitted}


def fixture_suffix():
    # Upstream test bodies and fixture construction remain unchanged. This
    # adapter adds one real attachment and supplies the prepared equivalent.
    return '''
# Gaia test-fixture adapter (same bytes in every comparison arm).
import os as _gaia_os
from case_support import extend_fixture as _gaia_extend, verify_fixture as _gaia_verify
_gaia_original_seed = todo_setup.__wrapped__
def _gaia_seed(user_model):
    _gaia_original_seed(user_model)
    _gaia_extend()
@pytest.fixture
def todo_setup(django_user_model, db):
    if _gaia_os.environ.get("GAIA_PREPARED") != "1":
        _gaia_seed(django_user_model)
    _gaia_verify()
'''


def root_conftest():
    return '''
import os
import pytest
if os.environ.get("GAIA_PREPARED") == "1":
    @pytest.fixture(scope="session")
    def django_db_setup(django_test_environment, django_db_blocker):
        # The controller supplied a private, migrated fixture database.
        # pytest-django still owns per-test transactions and teardown.
        with django_db_blocker.unblock():
            from django.db import connection
            assert "todo_task" in connection.introspection.table_names()
        yield
'''


def probe_source():
    return '''
import json, os, signal
from pathlib import Path
import pytest
from case_support import verify_fixture

@pytest.mark.django_db
def test_generation_and_resources(todo_setup):
    Path(os.environ["GAIA_PROBE"]).write_text(json.dumps(verify_fixture(), sort_keys=True))

@pytest.mark.django_db(transaction=True)
def test_successful_effects(todo_setup):
    _commit_effects()

@pytest.mark.django_db(transaction=True)
def test_committed_effects(todo_setup):
    _commit_effects()
    if os.environ["GAIA_FAULT"] == "kill":
        os.kill(os.getpid(), signal.SIGKILL)
    raise AssertionError("injected failure after committed effects")

def _commit_effects():
    from django.db import connection
    from django.conf import settings
    import todo.models
    assert connection.get_autocommit()
    task = todo.models.Task.objects.first()
    task.title = "committed request mutation"
    task.save()
    assert todo.models.Task.objects.get(pk=task.pk).title == "committed request mutation"
    Path(settings.MEDIA_ROOT, "leaked.txt").write_text("request-only")
    todo.models._gaia_leaked_heap = "dirty"
    Path(os.environ["GAIA_PROBE"]).write_text(json.dumps({"committed": True, "media_written": True, "heap_mutated": True}))
'''
