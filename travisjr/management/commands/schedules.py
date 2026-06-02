from django.core.management.base import BaseCommand

from django_q.models import Schedule


class Command(BaseCommand):

    def handle(self, *args, **options):

        Schedule.objects.get_or_create(
            name="Cleanup Expired Sessions",
            defaults={
                "func": "travisjr.tasks.cleanup_expired_sessions",
                "schedule_type": Schedule.CRON,
                "cron": "0 */2 * * *",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Cleanup schedule created successfully"
            )
        )
        # to run python manage.py schedules.py