from rest_framework import serializers
from ..models import GroupChat, GroupMembership, Hobby
from ..models import CustomUser

class GroupChatSerializer(serializers.ModelSerializer):
    admin = serializers.StringRelatedField()
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = GroupChat
        fields = [
            'id', 'name', 'description', 'group_type',
            'hobbies', 'city', 'institution', 'image', 'admin', 'members_count',
            'created_at',
        ]
        read_only_fields = ['admin', 'created_at']

    def get_members_count(self, obj):
        return obj.members.count()


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupChat
        fields = [
            'name', 'description', 'group_type',
            'hobbies', 'city', 'institution', 'image'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        group = GroupChat.objects.create(**validated_data)
        read_only_fields = ['admin', 'created_at'] 
        return group


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'group', 'role', 'joined_at']


class GroupJoinLeaveSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()

    def validate_group_id(self, value):
        try:
            GroupChat.objects.get(id=value)
        except GroupChat.DoesNotExist:
            raise serializers.ValidationError("Group does not exist.")
        return value


class SuggestedGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupChat
        fields = ['id', 'name', 'description', 'group_type', 'image', 'city', 'institution']


class HobbySerializer(serializers.ModelSerializer):
    class Meta:
        model = Hobby
        fields = ['id', 'name']
