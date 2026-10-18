(() => {
const select = document.querySelector('#query-select');
let status = document.querySelector('#predefined-status');
let results = document.querySelector('#predefined-results');
let source = document.querySelector('#predefined-source');
const reload = document.querySelector('#reload-results');
const mode = document.querySelector('#query-mode');
const predefinedControls = document.querySelector('#predefined-controls');
const graphControls = document.querySelector('#graph-controls');
let answers = [];
let graphAnswer = null;
let savedStatus = 'Loading query results...';

function showMode() {
  const predefined = mode.value === 'predefined';
  predefinedControls.hidden = !predefined;
  graphControls.hidden = predefined;
  const prefix = predefined ? 'predefined' : 'graph';
  status = document.querySelector(`#${prefix}-status`);
  results = document.querySelector(`#${prefix}-results`);
  source = document.querySelector(`#${prefix}-source`);
  results.replaceChildren();
  source.textContent = '';
  if (predefined) {
    if (answers.length) showAnswer();
    else status.textContent = savedStatus;
  } else if (graphAnswer) {
    if (graphAnswer.refused) {
      source.textContent = graphAnswer.query || '';
      status.textContent = graphAnswer.refused;
    } else renderAnswer(graphAnswer, false);
  } else status.textContent = 'Ask a question above to see its answer here.';
}
mode.addEventListener('change', showMode);

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
  return labels[column] ?? column.replace(/_/g, ' ').replace(/^./, letter => letter.toUpperCase());
}

function renderAnswer(answer, saved = true) {
  results.replaceChildren();
  source.textContent = answer.query;
  if (typeof answer.rows === 'boolean') {
    status.textContent = `Answer: ${answer.rows ? 'Yes' : 'No'}`;
    results.textContent = String(answer.rows);
    return;
  }
  status.textContent = `${answer.rows.length} result row${answer.rows.length === 1 ? '' : 's'}. ${saved ? 'Saved pipeline results; reload after rerunning the pipeline.' : 'Executed against the graph using the course access layer.'}`;
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

function showAnswer() {
  if (mode.value === 'predefined' && answers.length) renderAnswer(answers[Number(select.value)]);
}

async function loadAnswers() {
  const previous = select.value;
  select.disabled = true;
  reload.disabled = true;
  savedStatus = 'Loading query results...';
  if (mode.value === 'predefined') showMode();
  try {
    const response = await fetch('build/answers.json', {cache: 'no-store'});
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
    savedStatus = 'Cannot load results. From the repository root, run python run.py, then reload results. Open this page through the local HTTP server.';
    if (mode.value === 'predefined') status.textContent = savedStatus;
  } finally {
    reload.disabled = false;
  }
}
select.addEventListener('change', showAnswer);
reload.addEventListener('click', loadAnswers);
loadAnswers();

const askForm = document.querySelector('#ask-form');
const askButton = document.querySelector('#ask-button');
const askStatus = document.querySelector('#ask-status');
askForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (mode.value !== 'graph') return;
  const question = document.querySelector('#question').value.trim();
  if (!question) return;
  askButton.disabled = true;
  graphAnswer = null;
  if (mode.value === 'graph') showMode();
  askStatus.textContent = 'Asking the configured Gemini model and checking its SPARQL query. This may take a minute.';
  try {
    const response = await fetch(`/api/ask?${new URLSearchParams({question})}`, {cache: 'no-store'});
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new Error('Start the application with python run.py. A static-only server cannot answer natural-language questions.');
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The access layer could not answer this question.');
    graphAnswer = {question, ...result};
    if (mode.value === 'graph') showMode();
    askStatus.textContent = result.refused || `Answered in ${(result.attempts || []).length} attempt(s).`;
  } catch (error) {
    askStatus.textContent = error.message;
  } finally {
    askButton.disabled = false;
  }
});

})();
