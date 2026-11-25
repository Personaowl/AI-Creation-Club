from rest_framework import serializers

from .models import Asset, Work
from .policies import can_download_work, can_edit_work


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ("id", "original_name", "extension", "kind", "size")


class WorkWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        fields = ("title", "description", "competition_name", "team_name", "team_members")


class WorkSerializer(serializers.ModelSerializer):
    assets = AssetSerializer(many=True, read_only=True)
    can_download = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    review_note = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = (
            "id", "title", "description", "competition_name", "team_name", "team_members", "status", "is_visible", "assets",
            "created_at", "updated_at", "is_mine", "can_edit", "can_download", "review_note",
        )

    def get_can_download(self, work):
        return can_download_work(self.context["request"].user, work)

    def get_can_edit(self, work):
        return can_edit_work(self.context["request"].user, work)

    def get_is_mine(self, work):
        return work.owner_id == self.context["request"].user.pk

    def get_review_note(self, work):
        user = self.context["request"].user
        return work.review_note if user.is_superuser or user.pk == work.owner_id else ""


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=(Work.Status.APPROVED, Work.Status.REJECTED))
    note = serializers.CharField(max_length=1000, allow_blank=True, default="")


class AccessSerializer(serializers.Serializer):
    is_visible = serializers.BooleanField(required=False)
    allow_download = serializers.BooleanField(required=False)
