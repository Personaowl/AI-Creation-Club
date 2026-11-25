def active(user):
    return user.is_authenticated and user.is_active


def can_view_work(user, work):
    return active(user) and (user.is_superuser or work.owner_id == user.pk or work.published)


def can_download_work(user, work):
    return active(user) and (user.is_superuser or (work.published and work.allow_download))


def can_edit_work(user, work):
    return active(user) and work.owner_id == user.pk and work.status in (work.Status.DRAFT, work.Status.REJECTED)


def can_revise_work(user, work):
    return active(user) and work.owner_id == user.pk and work.status == work.Status.APPROVED and work.revision_of_id is None
