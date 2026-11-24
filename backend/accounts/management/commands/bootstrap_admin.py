import getpass
import os

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = "Create the initial AI Creation Club administrator."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("ENTRYSTAGE_ADMIN_USERNAME", "admin"))
        parser.add_argument("--no-input", action="store_true")

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options["username"]
        existing = user_model.objects.filter(username=username).first()
        if existing:
            if existing.is_superuser and existing.is_active:
                self.stdout.write("Administrator already exists.")
                return
            raise CommandError("The administrator username belongs to an existing account.")

        password = os.environ.get("ENTRYSTAGE_ADMIN_PASSWORD")
        if not password:
            if options["no_input"]:
                raise CommandError("Set ENTRYSTAGE_ADMIN_PASSWORD or omit --no-input.")
            password = getpass.getpass("Admin password: ")
            if password != getpass.getpass("Confirm admin password: "):
                raise CommandError("Passwords do not match.")
        user = user_model(username=username, is_staff=True, is_superuser=True)
        try:
            user.full_clean(exclude=["password"])
            password_validation.validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        try:
            with transaction.atomic():
                user.set_password(password)
                user.save()
        except IntegrityError as error:
            raise CommandError("The administrator username already exists.") from error
        self.stdout.write(self.style.SUCCESS(f"Administrator {username} created."))
