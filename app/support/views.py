from audit.service import record
from core.access import any_role, require_roles
from core.principal import Role
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from support.config import get_support_config
from support.events import IssueViewed
from support.forms import TYPE_GUIDANCE, IssueForm
from support.models import SupportIssue
from support.service import raise_issue, recent_issue_count

LIST_LIMIT = 200


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _form_response(request: HttpRequest, form: IssueForm, status: int = 200) -> HttpResponse:
    context = {"form": form, "guidance": TYPE_GUIDANCE}
    template = "support/_form.html" if _is_htmx(request) else "support/new.html"
    return render(request, template, context, status=status)


@any_role
def new_issue(request: HttpRequest) -> HttpResponse:
    """Report an issue: loaded into the dialog by HTMX, or as a full page without script."""
    if request.method != "POST":
        initial = {
            "page": request.GET.get("from", ""),
            "page_correlation_id": request.GET.get("cid", ""),
        }
        return _form_response(request, IssueForm(initial=initial))

    form = IssueForm(request.POST)
    if not form.is_valid():
        return _form_response(request, form, status=422)
    limit = get_support_config().rate_limit_per_hour
    if recent_issue_count(request.principal.object_id) >= limit:
        form.add_error(
            None, f"You have raised {limit} issues in the last hour. Please try again later."
        )
        return _form_response(request, form, status=429)

    issue = raise_issue(
        request,
        form.issue_fields(),
        page_url=form.cleaned_data["page"],
        page_correlation_id=form.cleaned_data["page_correlation_id"],
    )
    template = "support/_submitted.html" if _is_htmx(request) else "support/submitted.html"
    return render(request, template, {"issue": issue}, status=201)


@require_roles(Role.SUPPORT)
def issue_list(request: HttpRequest) -> HttpResponse:
    issues = SupportIssue.objects.prefetch_related("deliveries")[:LIST_LIMIT]
    return render(request, "support/issue_list.html", {"issues": issues, "limit": LIST_LIMIT})


@require_roles(Role.SUPPORT)
def issue_detail(request: HttpRequest, reference: str) -> HttpResponse:
    issue = SupportIssue.objects.prefetch_related("deliveries").filter(reference=reference).first()
    if issue is None:
        raise Http404("No such issue.")
    # Viewing full issue detail is data access, so it is audited before the page is shown.
    record(request, IssueViewed(reference=issue.reference), target=issue.reference)
    return render(request, "support/issue_detail.html", {"issue": issue})
