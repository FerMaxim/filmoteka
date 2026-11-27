from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from collection.services import add_to_library, library_for
from .models import Work


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=300, label="Название произведения")


class AddForm(forms.Form):
    added = forms.ChoiceField(choices=[("true", "Добавить")])


@login_required
@require_GET
def catalog(request):
    form = SearchForm(request.GET)
    works = Work.objects.none()
    status = 200
    if form.is_valid():
        works = Work.objects.filter(title__icontains=form.cleaned_data["q"])
    else:
        status = 422
    return render(
        request,
        "catalog/list.html",
        {"form": form, "page": Paginator(works, 24).get_page(request.GET.get("page"))},
        status=status,
    )


@login_required
@require_GET
def detail(request, pk):
    work = get_object_or_404(Work, pk=pk)
    saved = library_for(request.user).filter(work=work).exists()
    return render(request, "catalog/detail.html", {"work": work, "saved": saved})


@login_required
@require_GET
def library(request):
    return render(
        request,
        "collection/library.html",
        {
            "page": Paginator(library_for(request.user), 24).get_page(
                request.GET.get("page")
            )
        },
    )


@login_required
@require_POST
def add(request, pk):
    work = get_object_or_404(Work, pk=pk)
    form = AddForm(request.POST)
    if set(request.POST) - {"csrfmiddlewaretoken", "added"} or not form.is_valid():
        return render(
            request,
            "catalog/detail.html",
            {
                "work": work,
                "error": "Не удалось добавить произведение. Повторите действие кнопкой ниже.",
            },
            status=422,
        )
    add_to_library(owner=request.user, work=work)
    return HttpResponse(status=303, headers={"Location": "/me/library/"})
