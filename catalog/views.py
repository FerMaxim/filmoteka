from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from collection.services import add_to_library, library_for
from .models import ExternalRef, Work
from . import provider
from .presentation import present
from .kinopoisk import Unavailable
from django.conf import settings


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=300, label="Название произведения")


class ExternalSearchForm(SearchForm):
    external_page = forms.IntegerField(
        required=False, min_value=1, max_value=20, initial=1
    )


class ImportForm(forms.Form):
    external_id = forms.IntegerField(min_value=1, max_value=15000000)
    q = forms.CharField(max_length=300)
    external_page = forms.IntegerField(min_value=1, max_value=20)


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
        if not settings.KINOPOISK_DATA_APPROVED:
            works = works.exclude(external_refs__provider="kinopoisk_unofficial")
    else:
        status = 422
    return render(
        request,
        "catalog/list.html",
        {
            "form": form,
            "page": Paginator(works, 24).get_page(request.GET.get("page")),
            "query": form.cleaned_data.get("q", "") if form.is_valid() else "",
            "posters_enabled": settings.KINOPOISK_POSTERS_APPROVED,
        },
        status=status,
    )


@login_required
@require_GET
def detail(request, pk):
    work = get_object_or_404(Work, pk=pk)
    saved = library_for(request.user).filter(work=work).exists()
    return render(
        request,
        "catalog/detail.html",
        {
            "work": present(work),
            "saved": saved,
            "posters_enabled": settings.KINOPOISK_POSTERS_APPROVED,
        },
    )


@login_required
@require_GET
def library(request):
    page = Paginator(library_for(request.user), 24).get_page(request.GET.get("page"))
    if not settings.KINOPOISK_DATA_APPROVED:
        for entry in page:
            entry.work = present(entry.work)
    return render(
        request,
        "collection/library.html",
        {
            "posters_enabled": settings.KINOPOISK_POSTERS_APPROVED,
            "page": page,
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
                "work": present(work),
                "error": "Не удалось добавить произведение. Повторите действие кнопкой ниже.",
            },
            status=422,
        )
    add_to_library(owner=request.user, work=work)
    return HttpResponse(status=303, headers={"Location": "/me/library/"})


@login_required
@require_GET
def external_search(request):
    form = ExternalSearchForm(request.GET)
    if not form.is_valid() or not form.cleaned_data["q"]:
        return HttpResponse("Некорректный поисковый запрос.", status=422)
    query = form.cleaned_data["q"]
    page = form.cleaned_data["external_page"] or 1
    payload, notice = provider.search(query, page)
    # A local match on any local page must not also appear as an external card.
    local_ids = set(
        ExternalRef.objects.filter(
            provider="kinopoisk_unofficial", work__title__icontains=query
        ).values_list("external_id", flat=True)
    )
    items = [row for row in payload["items"] if row["external_id"] not in local_ids]
    return render(
        request,
        "catalog/external.html",
        {
            "items": items,
            "notice": notice,
            "query": query,
            "external_page": page,
            "next_external_page": page + 1 if page < payload["pages"] else None,
            "posters_enabled": settings.KINOPOISK_POSTERS_APPROVED,
        },
    )


@login_required
@require_POST
def import_selected(request):
    form = ImportForm(request.POST)
    if (
        set(request.POST) - {"csrfmiddlewaretoken", "external_id", "q", "external_page"}
        or not form.is_valid()
    ):
        return HttpResponse("Некорректное добавление произведения.", status=422)
    try:
        work = provider.import_work(
            form.cleaned_data["external_id"],
            form.cleaned_data["q"],
            form.cleaned_data["external_page"],
        )
    except Unavailable:
        return render(
            request,
            "catalog/import_error.html",
            {"query": form.cleaned_data["q"]},
            status=503,
        )
    add_to_library(owner=request.user, work=work)
    return HttpResponse(status=303, headers={"Location": f"/works/{work.pk}/"})
