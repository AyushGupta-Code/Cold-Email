from sqlalchemy import delete

from app.core.config import Settings
from app.db.session import SessionLocal, init_db
from app.models.entities import SearchCache
from app.schemas.api import JobSummary, ResumeSummary
from app.services.contact_discovery import FetchedPage, discover_contacts


def test_contact_search_pipeline_with_mocked_search_fetch_and_ollama(monkeypatch) -> None:
    init_db()
    with SessionLocal() as db:
        db.execute(delete(SearchCache))
        db.commit()

    def fake_expand_queries(job_summary, resume_summary, db, settings):
        return (
            [
                "Acme recruiter united states linkedin",
                "Acme hiring manager backend engineer united states",
            ],
            [],
            True,
        )

    def fake_retrieve_results(queries, db, settings):
        return (
            [
                {
                    "title": "Jamie Carter - Senior Recruiter - Acme | LinkedIn",
                    "snippet": "Austin, TX. Senior Recruiter at Acme focused on engineering hiring across the United States.",
                    "url": "https://www.linkedin.com/in/jamie-carter-acme",
                    "query": queries[0],
                    "search_source": "mock",
                },
                {
                    "title": "Morgan Lee | Acme recruiting team",
                    "snippet": "Morgan Lee leads backend hiring for Acme in Seattle, WA.",
                    "url": "https://acme.example/team/morgan-lee",
                    "query": queries[1],
                    "search_source": "mock",
                },
                {
                    "title": "Priya Shah - Talent Acquisition - Acme",
                    "snippet": "Toronto, Canada. Talent Acquisition Partner at Acme.",
                    "url": "https://www.linkedin.com/in/priya-shah-acme",
                    "query": queries[0],
                    "search_source": "mock",
                },
            ],
            [],
        )

    def fake_fetch_pages(results, db, settings, *, already_fetched=None, page_limit=None, aggressive=False):
        return [], []

    def fake_fetch_page(url, db, settings):
        if "jamie-carter" in url:
            return FetchedPage(
                url=url,
                text="Jamie Carter Senior Recruiter Acme Austin, TX",
                html="""
                <html><head>
                  <title>Jamie Carter | LinkedIn</title>
                  <meta property="og:title" content="Jamie Carter | Senior Recruiter at Acme">
                  <meta property="og:description" content="Jamie Carter Senior Recruiter Acme Austin, TX">
                  <meta property="og:image" content="https://media.licdn.com/jamie-carter.jpg">
                </head><body></body></html>
                """,
                fetch_method="requests",
                error=None,
            )
        return FetchedPage(url=url, text="", html="", fetch_method="requests", error="not mocked")

    def fake_extract_candidates(*, source_url, source_type, source_text, job_summary, settings, db):
        if "jamie-carter" in source_url:
            return (
                [
                    {
                        "name": "Jamie Carter",
                        "title": "Senior Recruiter",
                        "company": "Acme",
                        "location": "Austin, TX",
                        "profile_url": source_url,
                        "public_email": None,
                        "evidence": [
                            {
                                "source_url": source_url,
                                "source_type": source_type,
                                "quoted_text": "Senior Recruiter at Acme focused on engineering hiring across the United States",
                            }
                        ],
                    }
                ],
                [],
                True,
            )
        if "priya-shah" in source_url:
            return (
                [
                    {
                        "name": "Priya Shah",
                        "title": "Talent Acquisition Partner",
                        "company": "Acme",
                        "location": "Toronto, Canada",
                        "profile_url": source_url,
                        "public_email": None,
                        "evidence": [
                            {
                                "source_url": source_url,
                                "source_type": source_type,
                                "quoted_text": "Toronto, Canada. Talent Acquisition Partner at Acme.",
                            }
                        ],
                    }
                ],
                [],
                True,
            )
        return [], [], True

    monkeypatch.setattr("app.services.contact_discovery.expand_queries_with_ollama", fake_expand_queries)
    monkeypatch.setattr("app.services.contact_discovery._retrieve_public_results", fake_retrieve_results)
    monkeypatch.setattr("app.services.contact_discovery._fetch_promising_pages", fake_fetch_pages)
    monkeypatch.setattr("app.services.contact_discovery._fetch_page", fake_fetch_page)
    monkeypatch.setattr("app.services.contact_discovery.extract_candidates_with_ollama", fake_extract_candidates)
    monkeypatch.setattr("app.services.contact_ranker.compute_rerank_scores", lambda *args, **kwargs: ({}, []))

    job_summary = JobSummary(
        company_name="Acme",
        normalized_company_name="Acme",
        position="Backend Engineer",
        job_description="Build internal recruiter systems with Python and FastAPI.",
        concise_summary="Backend engineer role focused on recruiter systems.",
        important_skills=["Python", "FastAPI"],
        keywords=["python", "fastapi"],
    )
    resume_summary = ResumeSummary(skills=["Python"], experience_bullets=["Built local recruiter search tooling"])
    settings = Settings(discovery_mode="live", discovery_use_llm_for_contact_search=True)

    with SessionLocal() as db:
        result = discover_contacts(job_summary, resume_summary, db, settings)

    assert len(result.contacts) == 1
    assert [contact.full_name for contact in result.contacts] == ["Jamie Carter"]
    assert result.contacts[0].public_email is None
    assert all(contact.has_profile_picture for contact in result.contacts)
    assert all(contact.profile_picture_url for contact in result.contacts)
    assert result.debug.llm_queries_generated == [
        "Acme recruiter united states linkedin",
        "Acme hiring manager backend engineer united states",
    ]
    assert result.debug.queries_generated
    assert result.debug.urls_considered == 2
    assert result.debug.pages_fetched == 1
    assert result.debug.candidates_extracted == 2
    assert result.debug.candidates_after_filtering == 1
    assert any("Filtered out 1 non-LinkedIn search results before extraction." == warning for warning in result.warnings)
    assert any("Only 1 credible US-based contacts found" == warning for warning in result.warnings)


def test_contact_search_runs_second_fetch_when_first_pass_is_thin(monkeypatch) -> None:
    init_db()
    with SessionLocal() as db:
        db.execute(delete(SearchCache))
        db.commit()

    fetch_modes: list[bool] = []

    def fake_expand_queries(job_summary, resume_summary, db, settings):
        return (["Acme recruiter united states linkedin"], [], True)

    def fake_retrieve_results(queries, db, settings):
        return (
            [
                {
                    "title": "Jamie Carter - Senior Recruiter - Acme | LinkedIn",
                    "snippet": "Senior Recruiter at Acme focused on engineering hiring across the United States.",
                    "url": "https://www.linkedin.com/in/jamie-carter-acme",
                    "query": queries[0],
                    "search_source": "mock",
                },
                {
                    "title": "Morgan Lee | Acme recruiting team",
                    "snippet": "Morgan Lee supports backend hiring for Acme.",
                    "url": "https://acme.example/team/morgan-lee",
                    "query": queries[0],
                    "search_source": "mock",
                },
            ],
            [],
        )

    def fake_fetch_pages(results, db, settings, *, already_fetched=None, page_limit=None, aggressive=False):
        fetch_modes.append(aggressive)
        return [], []

    def fake_fetch_page(url, db, settings):
        if "jamie-carter" in url:
            return FetchedPage(
                url=url,
                text="Jamie Carter Senior Recruiter Acme Austin, TX",
                html="""
                <html><head>
                  <title>Jamie Carter | LinkedIn</title>
                  <meta property="og:title" content="Jamie Carter | Senior Recruiter at Acme">
                  <meta property="og:description" content="Jamie Carter Senior Recruiter Acme Austin, TX">
                  <meta property="og:image" content="https://media.licdn.com/jamie-carter.jpg">
                </head><body></body></html>
                """,
                fetch_method="requests",
                error=None,
            )
        return FetchedPage(url=url, text="", html="", fetch_method="requests", error="not mocked")

    def fake_extract_candidates(*, source_url, source_type, source_text, job_summary, settings, db):
        if "jamie-carter" in source_url:
            return (
                [
                    {
                        "name": "Jamie Carter",
                        "title": "Senior Recruiter",
                        "company": "Acme",
                        "location": "Austin, TX",
                        "profile_url": source_url,
                        "public_email": None,
                        "evidence": [
                            {
                                "source_url": source_url,
                                "source_type": source_type,
                                "quoted_text": "Senior Recruiter at Acme focused on engineering hiring across the United States.",
                            }
                        ],
                    }
                ],
                [],
                True,
            )
        return [], [], True

    monkeypatch.setattr("app.services.contact_discovery.expand_queries_with_ollama", fake_expand_queries)
    monkeypatch.setattr("app.services.contact_discovery._retrieve_public_results", fake_retrieve_results)
    monkeypatch.setattr("app.services.contact_discovery._fetch_promising_pages", fake_fetch_pages)
    monkeypatch.setattr("app.services.contact_discovery._fetch_page", fake_fetch_page)
    monkeypatch.setattr("app.services.contact_discovery.extract_candidates_with_ollama", fake_extract_candidates)
    monkeypatch.setattr("app.services.contact_ranker.compute_rerank_scores", lambda *args, **kwargs: ({}, []))

    job_summary = JobSummary(
        company_name="Acme",
        normalized_company_name="Acme",
        position="Backend Engineer",
        job_description="Build internal recruiter systems with Python and FastAPI.",
        concise_summary="Backend engineer role focused on recruiter systems.",
        important_skills=["Python", "FastAPI"],
        keywords=["python", "fastapi"],
    )
    resume_summary = ResumeSummary(skills=["Python"], experience_bullets=["Built local recruiter search tooling"])
    settings = Settings(discovery_mode="live", discovery_use_llm_for_contact_search=True)

    with SessionLocal() as db:
        result = discover_contacts(job_summary, resume_summary, db, settings)

    assert fetch_modes == [False, True]
    assert len(result.contacts) == 1
    assert [contact.full_name for contact in result.contacts] == ["Jamie Carter"]
    assert all(contact.has_profile_picture for contact in result.contacts)
    assert result.debug.pages_fetched == 1
