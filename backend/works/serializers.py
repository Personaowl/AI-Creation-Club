from rest_framework import serializers

from .models import Asset, Competition, Work, WorkComment
from .policies import can_download_work, can_edit_work, can_revise_work


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ("id", "original_name", "extension", "kind", "size")


class WorkWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        fields = (
            "title", "description", "competition", "competition_name", "team_name", "team_members",
            "team_intro", "award_info", "ip_details",
        )

    def validate(self, attrs):
        if "competition" in attrs:
            competition = attrs["competition"]
            attrs["competition_name"] = competition.name if competition else ""
        return attrs


class WorkSerializer(serializers.ModelSerializer):
    assets = AssetSerializer(many=True, read_only=True)
    can_download = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    review_note = serializers.SerializerMethodField()
    competition_name = serializers.SerializerMethodField()
    can_revise = serializers.SerializerMethodField()
    revision = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = (
            "id", "title", "description", "competition", "competition_name", "team_name", "team_members",
            "team_intro", "award_info", "ip_details", "status", "is_visible", "assets",
            "created_at", "updated_at", "is_mine", "can_edit", "can_download", "review_note",
            "revision_of", "can_revise", "revision",
        )

    def get_can_download(self, work):
        return can_download_work(self.context["request"].user, work)

    def get_competition_name(self, work):
        return work.competition.name if work.competition_id else work.competition_name

    def get_can_edit(self, work):
        return can_edit_work(self.context["request"].user, work)

    def get_can_revise(self, work):
        return can_revise_work(self.context["request"].user, work)

    def get_revision(self, work):
        if self.get_can_revise(work):
            revision = getattr(work, "revision", None)
            if revision:
                return {"id": str(revision.pk), "status": revision.status}
        return None

    def get_is_mine(self, work):
        return work.owner_id == self.context["request"].user.pk

    def get_review_note(self, work):
        user = self.context["request"].user
        return work.review_note if user.is_superuser or user.pk == work.owner_id else ""


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=(Work.Status.APPROVED, Work.Status.REJECTED))
    note = serializers.CharField(max_length=1000, allow_blank=True, default="")


class ManagedWorkSerializer(WorkSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta(WorkSerializer.Meta):
        fields = WorkSerializer.Meta.fields + ("owner_username", "allow_download")


class AccessSerializer(serializers.Serializer):
    is_visible = serializers.BooleanField(required=False)
    allow_download = serializers.BooleanField(required=False)
    competition = serializers.PrimaryKeyRelatedField(queryset=Competition.objects.all(), allow_null=True, required=False)


class CompetitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competition
        fields = ("id", "name")

    def validate_name(self, value):
        return " ".join(value.split())


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = WorkComment
        fields = ("id", "author", "body", "created_at", "can_delete")

    def get_can_delete(self, comment):
        user = self.context["request"].user
        return user.is_superuser or user.pk == comment.author_id
