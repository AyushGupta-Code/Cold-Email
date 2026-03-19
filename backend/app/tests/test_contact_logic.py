from app.core.config import Settings
from app.db.session import SessionLocal, init_db
from app.models.entities import SearchCache
from app.schemas.api import ContactCandidate, ContactEvidence, JobSummary, ResumeSummary
from app.services.contact_discovery import (
    ExtractedContact,
    FetchedPage,
    _apply_profile_picture_filter,
    _build_heuristic_queries,
    _combine_queries,
    _extract_location,
    _merge_extracted_candidates,
    _parse_mojeek_results,
    _parse_yahoo_results,
    _provider_sequence,
    _retrieve_public_results,
    deduplicate_contacts,
)
from app.services.contact_ranker import is_recruiter_like_title, rank_contacts, title_bucket
from app.services.persistence import cache_search_results, get_cached_search
from app.utils.http import normalize_result_url
from sqlalchemy import delete


def test_recruiter_title_matching() -> None:
    assert is_recruiter_like_title("Senior Recruiter") is True
    assert is_recruiter_like_title("Talent Acquisition Partner") is True
    assert is_recruiter_like_title("Talent Acquisition Advisor") is True
    assert is_recruiter_like_title("Campus Recruiting Manager") is True
    assert is_recruiter_like_title("Engineering Manager") is False


def test_title_bucket_keeps_recruiting_titles_above_generic_titles() -> None:
    recruiter_bucket, recruiter_score = title_bucket("University Recruiter")
    generic_bucket, generic_score = title_bucket("Marketing Operations Manager")
    assert recruiter_bucket in {"recruiter", "talent"}
    assert generic_bucket == "other"
    assert recruiter_score > generic_score


def test_contact_deduplication_keeps_best_variant() -> None:
    contacts = [
        ContactCandidate(
            name="Jamie Carter",
            full_name="Jamie Carter",
            title="Recruiter",
            location="Austin, TX",
            company="Acme",
            profile_url="https://www.linkedin.com/in/jamie-carter",
            source_urls=["https://www.linkedin.com/in/jamie-carter"],
            evidence=[
                ContactEvidence(
                    source_url="https://www.linkedin.com/in/jamie-carter",
                    source_type="search_snippet",
                    quoted_text="Jamie Carter - Recruiter - Acme",
                )
            ],
            public_email=None,
            score=60,
            is_us_based=True,
        ),
        ContactCandidate(
            name="Jamie Carter",
            full_name="Jamie Carter",
            title="Senior Recruiter",
            location="Austin, TX",
            company="Acme",
            profile_url="https://www.linkedin.com/in/jamie-carter",
            source_urls=[
                "https://www.linkedin.com/in/jamie-carter",
                "https://acme.example/team/jamie-carter",
            ],
            evidence=[
                ContactEvidence(
                    source_url="https://acme.example/team/jamie-carter",
                    source_type="page",
                    quoted_text="Jamie Carter Senior Recruiter Austin, TX",
                )
            ],
            public_email="jamie.carter@acme.example",
            profile_picture_url="https://acme.example/images/jamie-carter.jpg",
            profile_picture_source_url="https://acme.example/team/jamie-carter",
            profile_picture_confidence=0.93,
            profile_picture_evidence=[
                {
                    "source_url": "https://acme.example/team/jamie-carter",
                    "source_type": "page",
                    "image_url": "https://acme.example/images/jamie-carter.jpg",
                    "discovery_method": "img_tag",
                    "context_text": "Jamie Carter Senior Recruiter",
                }
            ],
            has_profile_picture=True,
            score=80,
            is_us_based=True,
        ),
    ]
    deduped = deduplicate_contacts(contacts)
    assert len(deduped) == 1
    assert deduped[0].public_email == "jamie.carter@acme.example"
    assert deduped[0].has_profile_picture is True
    assert deduped[0].profile_picture_url == "https://acme.example/images/jamie-carter.jpg"
    assert len(deduped[0].evidence) == 2


def test_query_combination_keeps_heuristic_recruiter_queries_on_path() -> None:
    heuristic = [
        "Deloitte recruiter united states linkedin",
        "site:linkedin.com/in Deloitte recruiter us",
        "Deloitte talent acquisition usa",
        "Deloitte university recruiter us",
    ]
    llm = [
        "Deloitte consultant leadership page",
        "Deloitte company culture us",
        "Deloitte brand team united states",
    ]

    combined = _combine_queries(heuristic, llm, target_count=6)

    assert combined[0] == "site:linkedin.com/in Deloitte recruiter united states linkedin"
    assert combined[1] == heuristic[1]
    assert any("recruiter" in query.casefold() for query in combined[:4])
    assert all("site:linkedin.com/in" in query.casefold() for query in combined)


def test_heuristic_queries_cover_multiple_recruiter_search_families() -> None:
    job_summary = JobSummary(
        company_name="Deloitte",
        normalized_company_name="Deloitte",
        position="Software Engineer",
        job_description="Build internal engineering platforms.",
        concise_summary="Software engineer role focused on internal platforms.",
        important_skills=["Python", "FastAPI", "AWS"],
        keywords=["python", "fastapi", "aws"],
    )

    queries = _build_heuristic_queries(job_summary, target_count=30)

    assert len(queries) >= 30
    assert all("site:linkedin.com/in" in query.casefold() for query in queries)
    assert any('site:linkedin.com/in "Deloitte" "technical recruiter"' in query for query in queries)
    assert any("talent acquisition partner" in query.casefold() for query in queries)
    assert any("university recruiter" in query.casefold() for query in queries)
    assert any("campus recruiter" in query.casefold() or "campus recruiting" in query.casefold() for query in queries)
    assert any("engineering manager" in query.casefold() for query in queries)
    assert any(any(location in query for location in ("Seattle, WA", "Austin, TX", "New York, NY")) for query in queries)


def test_provider_sequence_adds_yahoo_and_mojeek_after_existing_sources() -> None:
    with_searxng = _provider_sequence(Settings(searxng_base_url="http://localhost:8080"))
    without_searxng = _provider_sequence(Settings(searxng_base_url=""))

    assert with_searxng == ["searxng", "duckduckgo_html", "bing_html", "yahoo_html", "mojeek_html"]
    assert without_searxng == ["duckduckgo_html", "bing_html", "yahoo_html", "mojeek_html"]


def test_parse_yahoo_results_extracts_title_snippet_and_url() -> None:
    html = """
    <html><body>
      <div class="algo">
        <h3 class="title"><a href="https://example.com/jamie">Jamie Carter - Recruiter</a></h3>
        <div class="compText">Jamie Carter is a recruiter at Acme in Austin, TX.</div>
      </div>
    </body></html>
    """

    results = _parse_yahoo_results(html, "acme recruiter", limit=5)

    assert results == [
        {
            "title": "Jamie Carter - Recruiter",
            "snippet": "Jamie Carter is a recruiter at Acme in Austin, TX.",
            "url": "https://example.com/jamie",
            "query": "acme recruiter",
            "search_source": "yahoo_html",
        }
    ]


def test_normalize_result_url_unwraps_yahoo_redirect_path() -> None:
    wrapped = (
        "https://r.search.yahoo.com/_ylt=AwrX/ RV=2/RE=1768968396/RO=10/"
        "RU=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fjamie-carter-acme%2F/RK=2/RS=abcdef"
    ).replace(" ", "")

    assert normalize_result_url(wrapped) == "https://www.linkedin.com/in/jamie-carter-acme/"


def test_parse_mojeek_results_extracts_title_snippet_and_url() -> None:
    html = """
    <html><body>
      <div class="result">
        <h2><a href="https://example.com/morgan">Morgan Lee | Acme recruiting team</a></h2>
        <p class="result-desc">Morgan Lee supports backend hiring for Acme in Seattle, WA.</p>
      </div>
    </body></html>
    """

    results = _parse_mojeek_results(html, "acme hiring manager", limit=5)

    assert results == [
        {
            "title": "Morgan Lee | Acme recruiting team",
            "snippet": "Morgan Lee supports backend hiring for Acme in Seattle, WA.",
            "url": "https://example.com/morgan",
            "query": "acme hiring manager",
            "search_source": "mojeek_html",
        }
    ]


def test_provider_is_disabled_for_rest_of_run_after_blocking_response(monkeypatch) -> None:
    calls = {"mojeek": 0}

    monkeypatch.setattr(
        "app.services.contact_discovery._provider_sequence",
        lambda settings: ["mojeek_html"],
    )

    def fake_search_mojeek(query, db, settings):
        calls["mojeek"] += 1
        return [], [f"Mojeek query failed for '{query}': 403 Client Error: Forbidden"]

    monkeypatch.setattr("app.services.contact_discovery._search_mojeek", fake_search_mojeek)

    settings = Settings(discovery_request_delay_ms=0, discovery_log_progress=False)
    _, warnings = _retrieve_public_results(["query one", "query two"], db=None, settings=settings)

    assert calls["mojeek"] == 1
    assert any("Mojeek is blocking automated HTML queries" in warning for warning in warnings)


def test_partial_candidates_merge_before_final_validation() -> None:
    merged = _merge_extracted_candidates(
        [
            ExtractedContact(
                name="Jamie Carter",
                title="Senior Recruiter",
                company="Acme",
                location=None,
                profile_url="https://www.linkedin.com/in/jamie-carter-acme",
                evidence=[
                    ContactEvidence(
                        source_url="https://www.linkedin.com/in/jamie-carter-acme",
                        source_type="search_snippet",
                        quoted_text="Jamie Carter - Senior Recruiter - Acme",
                    )
                ],
            ),
            ExtractedContact(
                name="Jamie Carter",
                title=None,
                company="Acme",
                location="Austin, TX",
                profile_url="https://www.linkedin.com/in/jamie-carter-acme",
                evidence=[
                    ContactEvidence(
                        source_url="https://acme.example/team/jamie-carter",
                        source_type="page",
                        quoted_text="Jamie Carter Austin, TX",
                    )
                ],
            ),
        ],
        target_company="Acme",
    )

    assert len(merged) == 1
    assert merged[0].title == "Senior Recruiter"
    assert merged[0].location == "Austin, TX"
    assert len(merged[0].evidence) == 2


def test_extract_location_cleans_linkedin_prefixes() -> None:
    assert _extract_location("Jamie Carter - Senior Recruiter - Acme | LinkedIn Austin, TX") == "Austin, TX"
    assert _extract_location("Taylor Kim LinkedIn Greater Seattle Area") == "Greater Seattle Area"


def test_empty_search_results_are_not_reused() -> None:
    init_db()
    with SessionLocal() as db:
        db.execute(delete(SearchCache))
        db.commit()

        cache_search_results(db, "duckduckgo_html", "deloitte recruiter us", [])
        assert get_cached_search(db, "duckduckgo_html", "deloitte recruiter us") is None


def test_final_rank_ordering_prefers_better_company_match_and_email(monkeypatch) -> None:
    monkeypatch.setattr("app.services.contact_ranker.compute_rerank_scores", lambda *args, **kwargs: ({}, []))

    job_summary = JobSummary(
        company_name="Acme",
        normalized_company_name="Acme",
        position="Backend Engineer",
        job_description="Build recruiter tooling",
        concise_summary="Backend engineer role working on recruiter tooling.",
        important_skills=["Python", "FastAPI"],
        keywords=["python", "fastapi"],
    )
    resume_summary = ResumeSummary(skills=["Python"], experience_bullets=["Built local search tooling"])
    settings = Settings()
    contacts = [
        ContactCandidate(
            name="Taylor Kim",
            full_name="Taylor Kim",
            title="Engineering Manager",
            location="Remote - United States",
            company="Acme",
            profile_url="https://acme.example/team/taylor-kim",
            source_urls=["https://acme.example/team/taylor-kim"],
            evidence=[
                ContactEvidence(
                    source_url="https://acme.example/team/taylor-kim",
                    source_type="page",
                    quoted_text="Taylor Kim Engineering Manager Acme Remote - United States",
                )
            ],
            profile_picture_url="https://acme.example/images/taylor-kim.jpg",
            profile_picture_source_url="https://acme.example/team/taylor-kim",
            profile_picture_confidence=0.78,
            profile_picture_evidence=[
                {
                    "source_url": "https://acme.example/team/taylor-kim",
                    "source_type": "page",
                    "image_url": "https://acme.example/images/taylor-kim.jpg",
                    "discovery_method": "img_tag",
                    "context_text": "Taylor Kim Engineering Manager Acme Remote - United States",
                }
            ],
            has_profile_picture=True,
            is_us_based=True,
        ),
        ContactCandidate(
            name="Jamie Carter",
            full_name="Jamie Carter",
            title="Senior Recruiter",
            location="Austin, TX",
            company="Acme",
            profile_url="https://www.linkedin.com/in/jamie-carter-acme",
            public_email="jamie.carter@acme.example",
            source_urls=["https://www.linkedin.com/in/jamie-carter-acme"],
            evidence=[
                ContactEvidence(
                    source_url="https://www.linkedin.com/in/jamie-carter-acme",
                    source_type="search_snippet",
                    quoted_text="Jamie Carter - Senior Recruiter - Acme",
                )
            ],
            profile_picture_url="https://acme.example/images/jamie-carter.jpg",
            profile_picture_source_url="https://acme.example/team/jamie-carter",
            profile_picture_confidence=0.96,
            profile_picture_evidence=[
                {
                    "source_url": "https://acme.example/team/jamie-carter",
                    "source_type": "page",
                    "image_url": "https://acme.example/images/jamie-carter.jpg",
                    "discovery_method": "img_tag",
                    "context_text": "Jamie Carter Senior Recruiter Austin, TX",
                }
            ],
            has_profile_picture=True,
            is_us_based=True,
        ),
    ]

    ranked, warnings = rank_contacts(contacts, job_summary, resume_summary, settings, db=None, limit=5)
    assert not warnings
    assert ranked[0].full_name == "Jamie Carter"


def test_valid_person_like_image_is_accepted() -> None:
    candidate = _build_contact_candidate("https://acme.example/team/jamie-carter")
    page = FetchedPage(
        url="https://acme.example/team/jamie-carter",
        text="Jamie Carter Senior Recruiter Acme Austin, TX",
        html="""
        <html><head><title>Jamie Carter | Acme Recruiting Team</title></head><body>
          <article class="team-card">
            <img src="/images/team/jamie-carter.jpg" alt="Jamie Carter headshot" width="240" height="240">
            <h2>Jamie Carter</h2>
            <p>Senior Recruiter</p>
            <p>Austin, TX</p>
          </article>
        </body></html>
        """,
        fetch_method="requests",
    )

    filtered, warnings, _ = _apply_profile_picture_filter([candidate], [page], db=None, settings=Settings())

    assert not warnings
    assert len(filtered) == 1
    assert filtered[0].has_profile_picture is True
    assert filtered[0].profile_picture_url == "https://acme.example/images/team/jamie-carter.jpg"
    assert filtered[0].profile_picture_source_url == "https://acme.example/team/jamie-carter"
    assert filtered[0].profile_picture_confidence >= 0.9


def test_logo_banner_and_default_avatar_are_rejected() -> None:
    logo_candidate = _build_contact_candidate("https://acme.example/team/logo-case")
    avatar_candidate = _build_contact_candidate("https://acme.example/team/avatar-case")
    pages = [
        FetchedPage(
            url="https://acme.example/team/logo-case",
            text="Jamie Carter Senior Recruiter Acme Austin, TX",
            html="""
            <html><head><title>Jamie Carter | Acme</title></head><body>
              <article>
                <img src="/assets/logo-banner.png" alt="Acme logo banner" width="640" height="120">
                <h2>Jamie Carter</h2><p>Senior Recruiter</p>
              </article>
            </body></html>
            """,
            fetch_method="requests",
        ),
        FetchedPage(
            url="https://acme.example/team/avatar-case",
            text="Jamie Carter Senior Recruiter Acme Austin, TX",
            html="""
            <html><head><title>Jamie Carter | Acme</title></head><body>
              <article>
                <img src="/images/default-avatar.png" alt="Default avatar" width="180" height="180">
                <h2>Jamie Carter</h2><p>Senior Recruiter</p>
              </article>
            </body></html>
            """,
            fetch_method="requests",
        ),
    ]

    filtered, warnings, _ = _apply_profile_picture_filter(
        [logo_candidate, avatar_candidate],
        pages,
        db=None,
        settings=Settings(),
    )

    assert not filtered
    assert any("Filtered out 2 contacts" in warning for warning in warnings)


def test_candidate_with_no_image_is_rejected() -> None:
    candidate = _build_contact_candidate("https://acme.example/team/jamie-no-photo")
    page = FetchedPage(
        url="https://acme.example/team/jamie-no-photo",
        text="Jamie Carter Senior Recruiter Acme Austin, TX",
        html="""
        <html><head><title>Jamie Carter | Acme</title></head><body>
          <article>
            <h2>Jamie Carter</h2>
            <p>Senior Recruiter</p>
          </article>
        </body></html>
        """,
        fetch_method="requests",
    )

    filtered, warnings, _ = _apply_profile_picture_filter([candidate], [page], db=None, settings=Settings())

    assert not filtered
    assert any("No contacts satisfied the public profile picture requirement" in warning for warning in warnings)


def test_name_proximity_prefers_the_candidate_headshot() -> None:
    candidate = _build_contact_candidate("https://acme.example/team/jamie-card")
    page = FetchedPage(
        url="https://acme.example/team/jamie-card",
        text="Jamie Carter Senior Recruiter Acme Austin, TX",
        html="""
        <html><head><title>Acme Recruiting Team</title></head><body>
          <header>
            <img src="/images/recruiting-banner.jpg" alt="Recruiting banner" width="1200" height="300">
          </header>
          <section class="team-grid">
            <article class="card">
              <img src="/images/team/jamie-carter.jpg" alt="Jamie Carter profile photo" width="220" height="240">
              <h2>Jamie Carter</h2>
              <p>Senior Recruiter</p>
            </article>
          </section>
        </body></html>
        """,
        fetch_method="requests",
    )

    filtered, _, _ = _apply_profile_picture_filter([candidate], [page], db=None, settings=Settings())

    assert len(filtered) == 1
    assert filtered[0].profile_picture_url == "https://acme.example/images/team/jamie-carter.jpg"


def test_ranking_prefers_better_image_backed_contact(monkeypatch) -> None:
    monkeypatch.setattr("app.services.contact_ranker.compute_rerank_scores", lambda *args, **kwargs: ({}, []))

    job_summary = JobSummary(
        company_name="Acme",
        normalized_company_name="Acme",
        position="Backend Engineer",
        job_description="Build recruiter tooling",
        concise_summary="Backend engineer role working on recruiter tooling.",
        important_skills=["Python", "FastAPI"],
        keywords=["python", "fastapi"],
    )
    resume_summary = ResumeSummary(skills=["Python"], experience_bullets=["Built local search tooling"])
    settings = Settings()
    contacts = [
        _build_contact_candidate(
            "https://acme.example/team/alex-chen",
            name="Alex Chen",
            profile_picture_url="https://acme.example/images/alex-chen.jpg",
            profile_picture_source_url="https://acme.example/team/alex-chen",
            profile_picture_confidence=0.68,
            has_profile_picture=True,
        ),
        _build_contact_candidate(
            "https://acme.example/team/jamie-carter",
            profile_picture_url="https://acme.example/images/jamie-carter.jpg",
            profile_picture_source_url="https://acme.example/team/jamie-carter",
            profile_picture_confidence=0.97,
            has_profile_picture=True,
        ),
    ]

    ranked, warnings = rank_contacts(contacts, job_summary, resume_summary, settings, db=None, limit=5)

    assert not warnings
    assert ranked[0].full_name == "Jamie Carter"


def test_contact_candidate_backfills_new_profile_picture_fields() -> None:
    candidate = ContactCandidate.model_validate(
        {
            "full_name": "Jamie Carter",
            "title": "Senior Recruiter",
            "location": "Austin, TX",
            "company": "Acme",
            "profile_url": "https://acme.example/team/jamie-carter",
            "source_urls": ["https://acme.example/team/jamie-carter"],
            "evidence": [
                {
                    "source_url": "https://acme.example/team/jamie-carter",
                    "source_type": "page",
                    "quoted_text": "Jamie Carter Senior Recruiter Acme Austin, TX",
                }
            ],
            "is_us_based": True,
        }
    )

    assert candidate.full_name == "Jamie Carter"
    assert candidate.profile_picture_url is None
    assert candidate.profile_picture_source_url is None
    assert candidate.profile_picture_confidence == 0.0
    assert candidate.profile_picture_evidence == []
    assert candidate.has_profile_picture is False


def _build_contact_candidate(
    profile_url: str,
    *,
    name: str = "Jamie Carter",
    profile_picture_url: str | None = None,
    profile_picture_source_url: str | None = None,
    profile_picture_confidence: float = 0.0,
    has_profile_picture: bool = False,
) -> ContactCandidate:
    return ContactCandidate(
        name=name,
        full_name=name,
        title="Senior Recruiter",
        location="Austin, TX",
        company="Acme",
        profile_url=profile_url,
        source_urls=[profile_url],
        evidence=[
            ContactEvidence(
                source_url=profile_url,
                source_type="page",
                quoted_text=f"{name} Senior Recruiter Acme Austin, TX",
            )
        ],
        profile_picture_url=profile_picture_url,
        profile_picture_source_url=profile_picture_source_url,
        profile_picture_confidence=profile_picture_confidence,
        profile_picture_evidence=(
            [
                {
                    "source_url": profile_picture_source_url or profile_url,
                    "source_type": "page",
                    "image_url": profile_picture_url,
                    "discovery_method": "img_tag",
                    "context_text": f"{name} Senior Recruiter Acme Austin, TX",
                }
            ]
            if profile_picture_url and profile_picture_source_url
            else []
        ),
        has_profile_picture=has_profile_picture,
        is_us_based=True,
    )
