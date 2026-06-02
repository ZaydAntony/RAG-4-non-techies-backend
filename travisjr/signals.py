from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Session, ChatSession, Document


@receiver(post_delete, sender=Document)
def delete_document_file(sender, instance, **kwargs):
    """
    Removes the physical file from disk whenever a Document is deleted.
    """

    if instance.file:
        instance.file.delete(save=False)


#Intentionally create a default chat session to get the user started
@receiver(post_save, sender=Session)
def create_default_chat_session(sender, instance, created, **kwargs):
    if created:

        ChatSession.objects.create(
            session=instance
        )