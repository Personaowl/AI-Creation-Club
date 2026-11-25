from unicodedata import normalize

from django.db import migrations


def classify_existing_works(apps, schema_editor):
    Work = apps.get_model("works", "Work")
    Competition = apps.get_model("works", "Competition")
    database = schema_editor.connection.alias
    works = Work.objects.using(database)
    competitions = Competition.objects.using(database)
    records = works.exclude(competition_name="").order_by("created_at", "id")
    names = {}
    batch = []

    for work in records.only("id", "competition_name").iterator(chunk_size=500):
        name = " ".join(work.competition_name.split())
        if not name:
            continue
        key = normalize("NFC", name.casefold())
        if key not in names:
            competition, _ = competitions.get_or_create(name_key=key, defaults={"name": name})
            names[key] = competition.pk
        work.competition_id = names[key]
        batch.append(work)
        if len(batch) == 500:
            works.bulk_update(batch, ["competition"])
            batch.clear()

    if batch:
        works.bulk_update(batch, ["competition"])


class Migration(migrations.Migration):
    dependencies = [("works", "0004_competitions_and_comments")]
    operations = [migrations.RunPython(classify_existing_works, migrations.RunPython.noop)]
