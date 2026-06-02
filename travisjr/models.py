from django.db import models
from uuid import uuid4


class Session(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid4, editable=False)
    ip_address=models.GenericIPAddressField()
    user_agent=models.TextField(blank=True,null=True)
    message_count=models.IntegerField(default=0)
    expires_at=models.DateTimeField(db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)

class ChatSession(models.Model):
    title = models.CharField(max_length=255,null=True)
    session=models.ForeignKey(Session,on_delete=models.CASCADE, related_name='chat_sessions')
    created_at=models.DateTimeField(auto_now_add=True)

class Chats(models.Model):
    ROLES_CHOICES =[
        ("user", "user"),
        ("Ai_assistant", "assistant")
    ]
    chatsession=models.ForeignKey(ChatSession,on_delete=models.CASCADE,related_name='chats')
    chat=models.TextField()
    role =models.CharField(max_length=15, choices=ROLES_CHOICES)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['created_at']

class Document(models.Model):
    STATUS_CHOICES=[
        ('uploading', 'uploading'),
        ('processing', 'processing'),
        ('ready', 'ready'),
        ('error', 'error'),

    ]
    session=models.ForeignKey(Session,on_delete=models.CASCADE,related_name='docs')
    status=models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    file=models.FileField(upload_to='Docs/')
    file_name=models.CharField(max_length=100)
    uploaded_at=models.DateTimeField(auto_now_add=True)

class Chunk(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="chunks")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    # Optional but useful
    chunk_index = models.IntegerField(default=0)
    # If using external vector DB, store reference
    embedding_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    

