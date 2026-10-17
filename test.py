import arxiv

client = arxiv.Client(page_size=50, delay_seconds=3, num_retries=3)

search = arxiv.Search(
    query="cat:cs.CL AND submittedDate:[202610010000 TO 202610152359]",
    max_results=10,
    sort_by=arxiv.SortCriterion.SubmittedDate,
    sort_order=arxiv.SortOrder.Descending,
)

for r in client.results(search):
    print(f'ID : {r.get_short_id()}, PUBLISHED: {r.published}, {r.title}')
    print(r.pdf_url)