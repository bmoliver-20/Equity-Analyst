"""Extract reported release metrics without treating sales as total revenue.

Values retain the source's display units and strings. No totals are inferred.
"""
from datetime import datetime
import re

from bs4 import BeautifulSoup, NavigableString

DATE = re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.I)
MONTH_DAY = re.compile(DATE.pattern.replace(r',?\s+\d{4}\b', r',?'))
NUMBER = re.compile(r'^\(?-?\d[\d,]*(?:\.\d+)?\)?$')
DURATION = re.compile(r'\b(\d+|three|six|nine|twelve|thirteen|fourteen|fifteen|sixteen|fifty.two|fifty.three)\s+(weeks?|months?)\s+ended\b', re.I)
WORDS = {'three': 3, 'six': 6, 'nine': 9, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'fifty-two': 52, 'fifty-three': 53}


def period_kind(duration):
    match = DURATION.search(duration)
    if not match:
        return 'unknown'
    word = match[1].lower().replace(' ', '-')
    count = int(word) if word.isdigit() else WORDS.get(word)
    unit = match[2].lower()
    if (unit.startswith('month') and count == 3) or (unit.startswith('week') and count in {12, 13, 14, 15, 16}):
        return 'quarter'
    if (unit.startswith('month') and count == 12) or (unit.startswith('week') and count in {52, 53}):
        return 'annual'
    return 'year-to-date' if (unit.startswith('month') and count in {6, 9}) or (unit.startswith('week') and count in {26, 27, 39, 40}) else 'other'


def table_grid(table):
    """Map cells onto logical columns, honoring both rowspan and colspan."""
    occupied = {}
    rows = []
    for r, tr in enumerate(row for row in table.find_all('tr') if row.find_parent('table') is table):
        originals = []
        column = 0
        for cell in tr.find_all(['td', 'th'], recursive=False):
            while (r, column) in occupied:
                column += 1
            value = ' '.join(cell.get_text(' ', strip=True).split())
            width, height = int(cell.get('colspan', 1)), int(cell.get('rowspan', 1))
            entry = {'text': value, 'column': column, 'width': width}
            originals.append(entry)
            for dr in range(height):
                for dc in range(width):
                    occupied[r + dr, column + dc] = value
            column += width
        grid = {c: value for (row, c), value in occupied.items() if row == r}
        rows.append({'cells': originals, 'grid': grid, 'line': ' | '.join(c['text'] for c in originals)})
    return rows


def extract_release(html, source_url):
    """Return source rows plus independently labelled quarterly/annual cells.

    Unsupported or ambiguous headers do not produce an assigned metric value.
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = {'revenue': [], 'diluted_eps': []}
    for table in soup.find_all('table'):
        # Wrapper tables are not financial tables themselves.
        if table.find('table'):
            continue
        durations, dates, header_lines = {}, {}, []
        month_days, excluded_columns, basis_columns = {}, set(), {}
        section = ''
        nearby = []
        for node in table.previous_elements:
            if isinstance(node, NavigableString) and node.strip():
                nearby.append(str(node).strip())
                if len(nearby) >= 30:
                    break
        statement_title = next((line for line in nearby[:6] if re.search(r'consolidated statements of (?:income|operations|earnings)', line, re.I)), None)
        units = next((line for line in nearby if re.search(r'(?:dollars|amounts|\$) in (?:millions|thousands|billions)', line, re.I)), None)
        for row in table_grid(table):
            nonempty = [c for c in row['cells'] if c['text']]
            if not nonempty:
                continue
            # Assemble split date headers only from header rows, never data cells.
            is_duration = any(DURATION.search(c['text']) for c in nonempty)
            if is_duration:
                durations, dates, header_lines = {}, {}, []
                month_days, excluded_columns, basis_columns = {}, set(), {}
            is_year = (any(re.fullmatch(r'(?:19|20)\d{2}', c['text']) for c in nonempty)
                       and all(re.fullmatch(r'(?:19|20)\d{2}', c['text']) or re.search(r'amounts|dollars|percent change|adjusted|gaap|reported', c['text'], re.I) for c in nonempty))
            is_header = is_duration or is_year or any(MONTH_DAY.search(c['text']) for c in nonempty)
            is_header = is_header or (not any(NUMBER.fullmatch(c['text'].replace('$', '').strip()) for c in nonempty)
                                     and any(re.search(r'percent change|pre-tax impact|net impact|^(?:adjusted|reported|gaap|non-gaap)$', c['text'], re.I) for c in nonempty))
            if is_header:
                for column, value in row['grid'].items():
                    if re.search(r'percent change|pre-tax impact|tax impact|nci impact', value, re.I):
                        excluded_columns.add(column)
                    if re.search(r'adjusted|non-gaap', value, re.I):
                        basis_columns[column] = 'adjusted (non-GAAP)'
                    elif re.fullmatch(r'(?:reported|gaap)', value, re.I):
                        basis_columns[column] = 'GAAP (reported)'
                    if DURATION.search(value):
                        durations[column] = DURATION.search(value)[0]
                    if match := DATE.search(value):
                        raw = match[0]
                        try:
                            end = datetime.strptime(raw.replace(',', ''), '%B %d %Y').date().isoformat()
                        except ValueError:
                            continue
                        dates[column] = {'end': end, 'display': raw}
                    elif match := MONTH_DAY.search(value):
                        month_days[column] = match[0].rstrip(',')
                    elif re.fullmatch(r'(?:19|20)\d{2}', value) and column in month_days:
                        raw = month_days[column] + ', ' + value
                        try:
                            end = datetime.strptime(raw, '%B %d, %Y').date().isoformat()
                        except ValueError:
                            continue
                        dates[column] = {'end': end, 'display': raw}
                if row['line'] not in header_lines:
                    header_lines.append(row['line'])
                # Units are often on the same row as the year labels.
                if re.search(r'(?:dollars|amounts|\$) in (?:millions|thousands|billions)', row['line'], re.I):
                    units = nonempty[0]['text']
                continue
            if re.search(r'(?:dollars|amounts|\$) in (?:millions|thousands|billions)', row['line'], re.I):
                units = row['line']
            label = nonempty[0]['text']
            lower = label.lower().rstrip(':').strip()
            numeric = [c for c in nonempty[1:] if NUMBER.fullmatch(c['text'].replace('$', '').strip())]
            if not numeric:
                if re.search(r'per (?:common )?share|shares.*(?:calculation|outstanding)|weighted.average.*shares', lower):
                    section = label
                continue
            metric = None
            if re.fullmatch(r'total\s+(?:net\s+)?revenues?', lower):
                metric = 'revenue'
            elif (re.fullmatch(r'(?:reported|adjusted|gaap|non-gaap) eps', lower) and 'diluted' in section.lower()) or ('diluted' in lower and re.search(r'eps|per (?:common )?share', lower)) or (lower == 'diluted' and re.search(r'(?:income|earnings|loss).*per (?:common )?share', section, re.I)):
                metric = 'diluted_eps'
            if metric is None:
                continue
            values = []
            for cell in numeric:
                columns = range(cell['column'], cell['column'] + cell['width'])
                if any(c in excluded_columns for c in columns):
                    continue
                associations = {(durations[c], dates[c]['end'], dates[c]['display']) for c in columns if c in durations and c in dates}
                if len(associations) != 1 or any(c not in durations or c not in dates for c in columns):
                    continue
                duration, end, display = associations.pop()
                row_basis = 'adjusted (non-GAAP)' if re.search(r'adjusted|non-gaap', lower) else ('GAAP (reported)' if lower.startswith('reported ') or statement_title else 'reported (adjustment status not specified)')
                column_bases = {basis_columns[c] for c in columns if c in basis_columns}
                if len(column_bases) > 1:
                    continue
                basis = next(iter(column_bases), row_basis)
                values.append({'accounting_basis': basis, 'value': cell['text'], 'duration': duration, 'period_end': end, 'period_end_display': display, 'period_kind': period_kind(duration)})
            quarters = [v for v in values if v['period_kind'] == 'quarter']
            if not quarters:
                continue
            latest_end = max(v['period_end'] for v in quarters)
            for value in values:
                value['comparison'] = ('current quarter' if value['period_end'] == latest_end else 'comparative quarter') if value['period_kind'] == 'quarter' else value['period_kind']
            results[metric].append({'source_url': source_url, 'basis': 'reported, not calculated', 'units_source': (units if metric == 'revenue' or statement_title else 'Per share; currency symbol as printed in source row'), 'statement_title': statement_title, 'header_lines': header_lines.copy(), 'section_line': section if metric == 'diluted_eps' else None, 'source_line': row['line'], 'values': values})
    # Current/comparative labels use the whole release, including separate-year tables.
    for records in results.values():
        ends = [v['period_end'] for record in records for v in record['values'] if v['period_kind'] == 'quarter']
        if ends:
            latest = max(ends)
            for record in records:
                for value in record['values']:
                    if value['period_kind'] == 'quarter':
                        value['comparison'] = 'current quarter' if value['period_end'] == latest else 'comparative quarter'
    return results


def print_release(results):
    for metric, records in results.items():
        print(metric + ':')
        if not records:
            print('Unavailable: no reported total with unambiguous quarterly table headers was extracted. No substitute or calculated value used.')
        for record in records:
            print('Source URL: ' + record['source_url'])
            print('Basis: ' + record['basis'])
            print('Units source: ' + (record['units_source'] or 'not identified; consult source'))
            if record.get('statement_title'):
                print(record['statement_title'])
            print('Exact source rows (cell text preserved; | separates cells):')
            for line in record['header_lines']:
                print(line)
            if record['section_line']:
                print(record['section_line'])
            print(record['source_line'])
            for value in record['values']:
                print(f"  {value['comparison']}: {value['duration']} {value['period_end_display']} = {value['value']} [{value['accounting_basis']}]")
