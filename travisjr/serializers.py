from rest_framework import serializers
from .models import Session, ChatSession, Chats, Document, Chunk


class SessionsSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    chat_sessions = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = ["id", "chat_sessions"]

    def get_chat_sessions(self, obj):
        return [str(chat.id) for chat in obj.chat_sessions.all()]


class ChatSessionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ChatSession
        fields = ["id", "title"]

class ChatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chats
        fields = ["id","chat", "role"]
        read_only_fields = ["role"]

    def create(self, validated_data):
        chatsession_id=self.context['chatsession_id']
        return Chats.objects.create(chatsession=chatsession_id,**validated_data)



class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "status", "file", "file_name"]
        read_only_fields = ["status","file_name"]


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = ["id", "session", "document", "content", "chunk_index", "embedding_id"]
