import re
from unicodedata import normalize

from django.db import migrations


YEAR_PREFIX = re.compile(r"^((?:19|20)\d{2})\s*年\s*(.+)$")


def assign_existing_editions(apps, schema_editor):
    Competition = apps.get_model("works", "Competition")
    Edition = apps.get_model("works", "CompetitionEdition")
    Work = apps.get_model("works", "Work")
    database = schema_editor.connection.alias
    competitions = Competition.objects.using(database)
    editions = Edition.objects.using(database)
    works = Work.objects.using(database)
    groups = {}
    for item in competitions.order_by("id"):
        match = YEAR_PREFIX.fullmatch(item.name.strip())
        year = int(match[1]) if match else None
        name = " ".join(match[2].split()) if match else item.name
        key = normalize("NFC", name.casefold())
        groups.setdefault(key, []).append((item, name, year))

    for key, variants in groups.items():
        if all(year is None for _, _, year in variants):
            continue
        base, name, _ = next((variant for variant in variants if variant[2] is None), variants[0])
        for item, _, year in variants:
            if year is None:
                continue
            edition, _ = editions.get_or_create(competition_id=base.pk, year=year)
            works.filter(competition_id=item.pk).update(
                competition_id=base.pk, competition_name=name, competition_edition_id=edition.pk,
            )
            if item.pk != base.pk:
                competitions.filter(pk=item.pk).delete()
        if base.name != name:
            competitions.filter(pk=base.pk).update(name=name, name_key=key)


class Migration(migrations.Migration):
    dependencies = [("works", "0008_competition_editions")]
    operations = [migrations.RunPython(assign_existing_editions)]
