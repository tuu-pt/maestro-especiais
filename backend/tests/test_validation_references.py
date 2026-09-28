"""REF-01, REF-02, REF-03: citations found in the text and looked up in the corpus (task 4a)."""

import pytest

from app.validation import citations


@pytest.mark.parametrize(
    ("text", "found", "code"),
    [("IP XX (NP EN 60 529)", "NP EN 60 529", "np-en-60529"),
     ("segundo a norma EN60898", "EN60898", "en-60898"),
     ("a Portaria n.º 949-A/2006", "Portaria n.º 949-A/2006", "rtiebt"),
     ("Decreto de Lei n.º 226/2005, de 28", "Decreto de Lei n.º 226/2005", None),
     ("Decreto\u2011Lei n.º 96/2017", "Decreto\u2011Lei n.º 96/2017", "dl-96-2017"),
     ("detetores segundo a EN54", "EN54", None)],
)  # fmt: skip
def test_citations_are_found_and_looked_up_in_the_corpus(text: str, found: str,
                                                         code: str | None) -> None:  # fmt: skip
    cited = citations.find(text)
    assert cited[0].text == found and cited[0].code == code


@pytest.mark.parametrize(
    ("text", "incomplete"),
    [("Segundo a secção das RTIEBT, o espaço", True), ("nas secções da RTIEBT.", True),
     ("ao estipulado nas secções das RTIEBT.", True),
     ("à secção 801.2.1.3.2.1 das RTIEBT", False), ("segundo as RTIEBT", False)],
)  # fmt: skip
def test_a_section_of_the_rtiebt_without_its_number_c11(text: str, incomplete: bool) -> None:
    assert bool(citations.incomplete(text)) is incomplete
