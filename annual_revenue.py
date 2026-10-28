"""Validate consolidated annual revenue against filing labels and inline XBRL."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from bs4 import BeautifulSoup

TAGS = {'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'SalesRevenueNet'}


def revenue_evidence(html, source_url, accession):
    soup = BeautifulSoup(html, 'html.parser')
    contexts = {node.get('id'): node for node in soup.find_all(lambda x: x.name.lower().split(':')[-1] == 'context')}
    units = {node.get('id'): node.get_text(' ', strip=True) for node in soup.find_all(lambda x: x.name.lower().split(':')[-1] == 'unit')}
    # An explicitly inclusive definition is required to accept a row called net sales.
    definitions = []
    for node in soup.find_all(['p', 'div']):
        text = ' '.join(node.get_text(' ', strip=True).split())
        if len(text) < 1500 and re.search(r'net sales includes? merchandise sales and revenues? from other sources', text, re.I):
            definitions.append(text)
    definition = min(definitions, key=len, default=None)
    evidence = []
    for table in soup.find_all('table'):
        # A consolidated income-statement table must also contain operating income.
        if not table.find('ix:nonfraction', attrs={'name': 'us-gaap:OperatingIncomeLoss'}):
            continue
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'], recursive=False)
            if not cells:
                continue
            label = cells[0].get_text(' ', strip=True)
            is_total = re.fullmatch(r'total\s+revenues?', label, re.I)
            inclusive_sales = re.fullmatch(r'net sales', label, re.I) and definition
            if not (is_total or inclusive_sales):
                continue
            for node in row.find_all('ix:nonfraction'):
                tag = node.get('name', '')
                if tag.split(':')[-1] not in TAGS or not tag.startswith('us-gaap:'):
                    continue
                context = contexts.get(node.get('contextref'))
                if context is None or context.find(lambda x: x.name.lower().split(':')[-1] in {'explicitmember', 'typedmember'}):
                    continue
                start_node = context.find(lambda x: x.name.lower().split(':')[-1] == 'startdate')
                end_node = context.find(lambda x: x.name.lower().split(':')[-1] == 'enddate')
                if start_node is None or end_node is None:
                    continue
                start, end = start_node.text.strip(), end_node.text.strip()
                if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 380:
                    continue
                if units.get(node.get('unitref'), '').split(':')[-1] != 'USD':
                    continue
                try:
                    value = Decimal(node.get_text('', strip=True).replace(',', '').replace('$', '')) * (Decimal(10) ** int(node.get('scale', 0)))
                    if node.get('sign') == '-':
                        value = -value
                except (InvalidOperation, ValueError):
                    continue
                evidence.append({'tag': tag, 'start': start, 'end': end, 'val': int(value), 'unit': 'USD', 'accn': accession, 'context_id': node.get('contextref'), 'filing_label': label, 'definition': 'Consolidated total revenue as labelled in the income statement.' if is_total else definition, 'source_url': source_url, 'source_row': ' | '.join(c.get_text(' ', strip=True) for c in cells)})
    return evidence
