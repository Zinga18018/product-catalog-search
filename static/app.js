"use strict";

const $ = (selector) => document.querySelector(selector);
const form = $("#search-form");
const queryInput = $("#search-query");
const categoryInput = $("#category");
const minInput = $("#min-price");
const maxInput = $("#max-price");
const modeInput = $("#view-mode");
const resultsGrid = $("#results-grid");
const errorBox = $("#search-error");
const status = $("#search-status");
const submitButton = $(".search-button");
const resultSection = $(".results-section");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
let currentController = null;

const methodInfo = {
  tfidf: { name: "TF-IDF", subtitle: "Rare-word weighting · cosine similarity", letter: "A" },
  bm25: { name: "BM25", subtitle: "Term saturation · length normalization", letter: "B" },
};

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined && content !== null) element.textContent = String(content);
  return element;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = !message;
}

async function fetchJSON(url, signal) {
  const response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response. Please try again.");
  }
  if (!response.ok) throw new Error(data.error || `The request failed (${response.status}).`);
  return data;
}

function highlightText(element, text, matchedTerms) {
  const matches = new Set((matchedTerms || []).map((term) => String(term).toLowerCase()));
  const parts = String(text || "").split(/([\p{L}\p{N}]+)/u);
  for (const part of parts) {
    element.append(matches.has(part.toLowerCase()) ? node("mark", "", part) : document.createTextNode(part));
  }
}

function productCard(product, rank, hasQuery) {
  const card = node("li", "product-card");
  card.append(node("span", "rank-badge", String(rank).padStart(2, "0")));
  const content = node("div", "product-content");
  const top = node("div", "product-topline");
  const title = node("h4", "product-title");
  highlightText(title, product.title, product.matched_terms);
  top.append(title, node("span", "product-price", money.format(product.price_cents / 100)));
  const meta = node("div", "product-meta");
  meta.append(node("span", "category-badge", product.category), node("span", "product-id", product.id));
  const description = node("p", "product-description");
  highlightText(description, product.description, product.matched_terms);
  content.append(top, meta, description);
  if (Array.isArray(product.tags) && product.tags.length) {
    const tags = node("div", "product-tags");
    for (const tag of product.tags.slice(0, 4)) tags.append(node("span", "product-tag", tag));
    content.append(tags);
  }
  const matchLine = node("div", "match-line");
  const terms = node("div", "matched-terms");
  if (hasQuery && product.matched_terms?.length) {
    terms.append(node("span", "", "Matched"));
    for (const term of product.matched_terms) terms.append(node("span", "matched-term", term));
  } else {
    terms.append(node("span", "", hasQuery ? "No exact query terms" : "Catalog order"));
  }
  const score = node("span", "score");
  if (Number.isFinite(product.score)) score.append(document.createTextNode("Score"), node("strong", "", product.score.toFixed(4)));
  else score.textContent = "Unranked";
  matchLine.append(terms, score);
  content.append(matchLine);
  if (hasQuery && Array.isArray(product.explanation) && product.explanation.length) {
    const details = node("details", "explanation");
    details.append(node("summary", "", "Why this matched"), node("p", "", "Term contributions to this method’s score:"));
    const list = node("dl", "contribution-list");
    for (const item of product.explanation) {
      list.append(node("dt", "", item.term), node("dd", "", Number(item.contribution).toFixed(5)));
    }
    details.append(list);
    content.append(details);
  }
  card.append(content);
  return card;
}

function resultColumn(data, method) {
  const info = methodInfo[method];
  const column = node("section", "result-column");
  column.dataset.method = method;
  column.setAttribute("aria-label", `${info.name} results`);
  const heading = node("div", "column-heading");
  const left = node("div", "heading-left");
  const text = node("div");
  text.append(node("h3", "", info.name), node("p", "", info.subtitle));
  left.append(node("span", "method-letter", info.letter), text);
  const total = Number.isInteger(data.total) ? data.total : data.results.length;
  const count = data.results.length;
  heading.append(left, node("span", "result-count", `${count} of ${total} ${total === 1 ? "match" : "matches"}`));
  column.append(heading);
  if (!count) {
    const empty = node("div", "empty-state");
    empty.append(node("div", "empty-symbol", "∅"), node("h4", "", "No matches this time"), node("p", "", "Try a different word, broaden the category, or adjust the price range."));
    column.append(empty);
  } else {
    const list = node("ol", "product-list");
    data.results.forEach((product, index) => list.append(productCard(product, index + 1, Boolean(data.query.trim()))));
    column.append(list);
  }
  return column;
}

function readParams() {
  const params = new URLSearchParams({ q: queryInput.value.trim(), limit: "8" });
  if (categoryInput.value) params.set("category", categoryInput.value);
  if (minInput.value !== "") params.set("min_price", minInput.value);
  if (maxInput.value !== "") params.set("max_price", maxInput.value);
  return params;
}

function validateForm() {
  if (queryInput.value.length > 256) return "Keep the query to 256 characters or fewer.";
  for (const [name, input] of [["Minimum", minInput], ["Maximum", maxInput]]) {
    if (input.validity.badInput || (input.value !== "" && (!Number.isFinite(Number(input.value)) || Number(input.value) < 0))) {
      return `${name} price must be a nonnegative number.`;
    }
  }
  if (minInput.value !== "" && maxInput.value !== "" && Number(minInput.value) > Number(maxInput.value)) {
    return "Minimum price must be no greater than maximum price.";
  }
  return "";
}

function comparisonText(data, methods, query) {
  if (!query) return "Blank search shows catalog order. Add a query to compare ranking.";
  if (methods.length === 1) return `${methodInfo[methods[0]].name} results. Scores reflect this method only.`;
  const first = data[0].results.map((product) => product.id);
  const second = data[1].results.map((product) => product.id);
  if (!first.length && !second.length) return "Neither method found a matching product with these filters.";
  const overlap = first.filter((id) => second.includes(id)).length;
  const sameTop = first[0] && first[0] === second[0];
  return `${sameTop ? "Same top result" : "Different top results"} · ${overlap} shared in the displayed results. Raw score scales differ.`;
}

async function search() {
  const validationError = validateForm();
  if (validationError) {
    showError(validationError);
    return;
  }
  if (currentController) currentController.abort();
  const controller = new AbortController();
  currentController = controller;
  const methods = modeInput.value === "compare" ? ["tfidf", "bm25"] : [modeInput.value];
  const params = readParams();
  const query = params.get("q");
  showError("");
  resultsGrid.classList.toggle("single", methods.length === 1);
  resultsGrid.replaceChildren(node("div", "loading-state", "Searching the catalog…"));
  resultSection.setAttribute("aria-busy", "true");
  submitButton.disabled = true;
  status.textContent = "Searching the catalog.";
  try {
    const data = await Promise.all(methods.map((method) => {
      const methodParams = new URLSearchParams(params);
      methodParams.set("method", method);
      return fetchJSON(`/api/search?${methodParams}`, controller.signal);
    }));
    if (controller.signal.aborted) return;
    resultsGrid.replaceChildren(...data.map((result, index) => resultColumn(result, methods[index])));
    $("#results-title").textContent = query ? `Matches for “${query}”` : "Explore the catalog";
    $("#comparison-note").textContent = comparisonText(data, methods, query);
    status.textContent = `${query ? `Results for ${query}. ` : "Catalog loaded. "}${data.map((result, index) => `${methodInfo[methods[index]].name}: ${result.total} matches, ${result.results.length} shown`).join(". ")}.`;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams({ ...Object.fromEntries(params), view: modeInput.value }).toString();
    history.replaceState(null, "", url);
  } catch (error) {
    if (error.name === "AbortError") return;
    showError(error.message || "The search could not be completed. Please try again.");
    resultsGrid.replaceChildren(node("div", "loading-state", "Search unavailable. Check the server and try again."));
    resultsGrid.firstChild.classList.add("request-failed");
    status.textContent = "Search failed.";
  } finally {
    if (currentController === controller) {
      resultSection.setAttribute("aria-busy", "false");
      submitButton.disabled = false;
      currentController = null;
    }
  }
}

function renderEvaluation(evaluation) {
  // The server may omit evaluation until the reproducible evaluation script is run.
  if (!evaluation) return;
  const heldout = evaluation.splits?.heldout || evaluation.heldout;
  if (!heldout) return;
  const metrics = $("#evaluation-metrics");
  const cards = [];
  for (const method of ["tfidf", "bm25"]) {
    const result = heldout[method];
    if (!result || !Number.isFinite(result.mrr_at_k) || !Number.isFinite(result.recall_at_k)) continue;
    const k = result.k ?? evaluation.k ?? 5;
    const card = node("div", "metric-card");
    card.append(node("h3", "", methodInfo[method].name));
    const list = node("dl");
    list.append(node("dt", "", `MRR@${k}`), node("dd", "", result.mrr_at_k.toFixed(3)), node("dt", "", `Recall@${k}`), node("dd", "", result.recall_at_k.toFixed(3)));
    card.append(list);
    if (Number.isInteger(heldout.answerable_queries)) card.append(node("p", "", `${heldout.answerable_queries} answerable held-out queries`));
    cards.push(card);
  }
  if (cards.length) {
    metrics.replaceChildren(...cards);
    $("#evaluation-section").hidden = false;
  }
}

async function initialize() {
  const saved = new URLSearchParams(window.location.search);
  queryInput.value = saved.get("q") || "";
  minInput.value = saved.get("min_price") || "";
  maxInput.value = saved.get("max_price") || "";
  if (["compare", "tfidf", "bm25"].includes(saved.get("view"))) modeInput.value = saved.get("view");
  try {
    const meta = await fetchJSON("/api/meta");
    $("#product-count").textContent = meta.product_count;
    $("#category-count").textContent = String(meta.categories.length).padStart(2, "0");
    for (const category of meta.categories) {
      const option = node("option", "", category);
      option.value = category;
      categoryInput.append(option);
    }
    if (meta.categories.includes(saved.get("category"))) categoryInput.value = saved.get("category");
    renderEvaluation(meta.evaluation);
    await search();
  } catch (error) {
    showError(error.message || "Could not load the catalog. Check the local server.");
    status.textContent = "Catalog unavailable.";
  }
}

form.addEventListener("submit", (event) => { event.preventDefault(); search(); });
modeInput.addEventListener("change", search);
$("#clear-filters").addEventListener("click", () => {
  form.reset();
  modeInput.value = "compare";
  queryInput.focus();
  search();
});
for (const button of document.querySelectorAll(".example-chip")) {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.query;
    categoryInput.value = "";
    minInput.value = "";
    maxInput.value = "";
    search();
  });
}
initialize();
