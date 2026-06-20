import logging

from django.core.management.base import BaseCommand

from travisjr.tasks import cleanup_expired_sessions

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, *args, **options):
        total_deleted = cleanup_expired_sessions()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup complete. Removed {total_deleted} expired session(s)."
            )
        )