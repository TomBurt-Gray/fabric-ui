import re

from django import forms

from support.models import IMPACT_FLAGS, IssueType, SupportIssue

TYPE_GUIDANCE = {
    IssueType.INCIDENT: "Something that worked has stopped working.",
    IssueType.REQUEST: "You need something done, such as access or a data correction.",
    IssueType.DEFECT: "The application behaves differently from how it should.",
    IssueType.ENHANCEMENT: "An idea for a new feature or an improvement.",
}
# Only page paths on this site, never other hosts ("//host" is protocol relative).
_SAFE_PATH = re.compile(r"/(?!/)[^\s]{0,2047}")
_CORRELATION_ID = re.compile(r"[A-Za-z0-9._-]{8,128}")


class IssueForm(forms.ModelForm):
    page = forms.CharField(required=False, widget=forms.HiddenInput)
    page_correlation_id = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = SupportIssue
        fields = [
            "type",
            "subject",
            "description",
            "expected_behaviour",
            "actual_behaviour",
            "steps_to_reproduce",
            "workaround",
            *IMPACT_FLAGS,
        ]
        labels = {
            "description": "What is the problem or request?",
            "expected_behaviour": "What did you expect to happen?",
            "actual_behaviour": "What happened instead?",
            "workaround": "Is there a workaround in place?",
            **IMPACT_FLAGS,
        }
        widgets = {
            "type": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 4}),
            "expected_behaviour": forms.Textarea(attrs={"rows": 2}),
            "actual_behaviour": forms.Textarea(attrs={"rows": 2}),
            "steps_to_reproduce": forms.Textarea(attrs={"rows": 3}),
            "workaround": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = IssueType.choices  # No blank choice.

    def clean_page(self) -> str:
        page = self.cleaned_data["page"]
        return page if _SAFE_PATH.fullmatch(page) else ""

    def clean_page_correlation_id(self) -> str:
        value = self.cleaned_data["page_correlation_id"]
        return value if _CORRELATION_ID.fullmatch(value) else ""

    def issue_fields(self) -> dict:
        return {name: self.cleaned_data[name] for name in self.Meta.fields}
