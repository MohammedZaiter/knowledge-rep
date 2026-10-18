const select = document.querySelector('#query-select');
const status = document.querySelector('#query-status');
const results = document.querySelector('#query-results');
const source = document.querySelector('#query-source');
const reload = document.querySelector('#reload-results');
let answers = [];

function columnLabel(column, query) {
  const isCount = /\bCOUNT\s*\(/i.test(query);
  const labels = {
    f: 'Food URI', food: 'Food URI', c: 'Category URI',
    name: /\?n\s+a\s+food:Nutrient/.test(query) ? 'Nutrient name' : 'Food name',
    d: 'Publication date', unit: 'Unit',
    n: isCount ? (/COUNT\s*\(\?o\)/i.test(query) ? 'Observation count' : 'Food count') : 'Nutrient URI'
  };
  if (column === 'a') {
    const nutrients = {
      '1003': ['Protein', 'g'], '1004': ['Fat', 'g'],
      '1005': ['Carbohydrate', 'g'], '1079': ['Fiber', 'g'],
      '1093': ['Sodium', 'mg'], '2000': ['Sugars', 'g']
    };
    const id = query.match(/food:nutrient\s+nutrient:(\d+)/)?.[1];
    const nutrient = nutrients[id];
    return nutrient ? `${nutrient[0]} (${nutrient[1]} per 100 g)` : 'Amount per 100 g';
  }
  return labels[column] ?? column;
}

function showAnswer() {
  results.replaceChildren();
  const answer = answers[Number(select.value)];
  source.textContent = answer.query;
  if (typeof answer.rows === 'boolean') {
    status.textContent = `Answer: ${answer.rows ? 'Yes' : 'No'}`;
    results.textContent = String(answer.rows);
    return;
  }
  status.textContent = `${answer.rows.length} result row${answer.rows.length === 1 ? '' : 's'}. Saved pipeline results; reload after rerunning the pipeline.`;
  if (!answer.rows.length) {
    results.textContent = 'No matching results.';
    return;
  }
  const columns = [...new Set(answer.rows.flatMap(row => Object.keys(row)))];
  const table = document.createElement('table');
  const caption = document.createElement('caption');
  caption.textContent = answer.question;
  table.append(caption);
  const head = table.createTHead().insertRow();
  for (const column of columns) {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = columnLabel(column, answer.query);
    head.append(cell);
  }
  const body = table.createTBody();
  for (const row of answer.rows) {
    const tr = body.insertRow();
    for (const column of columns) tr.insertCell().textContent = row[column] ?? '';
  }
  results.append(table);
}

async function loadAnswers() {
  const previous = select.value;
  select.disabled = true;
  reload.disabled = true;
  results.replaceChildren();
  source.textContent = '';
  status.textContent = 'Loading query results...';
  try {
    const response = await fetch('food_project/build/answers.json', {cache: 'no-store'});
    if (!response.ok) throw new Error('Results unavailable');
    const data = await response.json();
    if (!Array.isArray(data) || !data.length || !data.every(answer =>
      typeof answer.question === 'string' && typeof answer.query === 'string' &&
      (typeof answer.rows === 'boolean' || (Array.isArray(answer.rows) && answer.rows.every(row => row && typeof row === 'object' && !Array.isArray(row))))
    )) throw new Error('Invalid results');
    answers = data;
    select.replaceChildren(...answers.map((answer, index) => new Option(`${index + 1}. ${answer.question}`, String(index))));
    if (previous && Number(previous) < answers.length) select.value = previous;
    select.disabled = false;
    showAnswer();
  } catch {
    select.replaceChildren(new Option('Results unavailable', ''));
    status.textContent = 'Cannot load results. From food_project, run .\\.venv\\Scripts\\python.exe run.py, then reload results. Open this page through the local HTTP server.';
  } finally {
    reload.disabled = false;
  }
}
select.addEventListener('change', showAnswer);
reload.addEventListener('click', loadAnswers);
loadAnswers();
