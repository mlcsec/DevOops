#!/usr/bin/env python3

import requests
from base64 import b64encode
import json
import sys
import argparse
import re
from typing import Optional, List, Dict, Set
from dataclasses import dataclass
from enum import Enum
import os 
import mimetypes
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tqdm import tqdm
import html
import uuid
import csv 
import io 
from colorama import init, Fore, Style

class Logger:
    # Initialize colorama to support ANSI colors on all platforms
    init(autoreset=True)

    # Define color and symbol mappings
    LEVELS = {
        'info': (Fore.CYAN, '*', Fore.WHITE),
        'info_repo': (Fore.CYAN, '>>', Fore.WHITE),
        'info_branch': (Fore.CYAN, '>', Fore.WHITE),
        'success': (Fore.GREEN, '+', Fore.WHITE),
        'success_report': (Fore.GREEN, '>>', Fore.WHITE),
        'warn': (Fore.YELLOW, '!', Fore.WHITE),
        'error': (Fore.RED, '-', Fore.WHITE)
    }

    def __init__(self, stream=sys.stdout, use_timestamp=True):
        """
        Initialize Logger
        
        Args:
            stream: Output stream (default: sys.stdout)
            use_timestamp: Whether to include timestamps (default: True)
        """
        self.stream = stream
        self.use_timestamp = use_timestamp

    def _format_message(self, message, *args):
        """
        Format message with optional arguments
        
        Args:
            message: Message template
            *args: Optional formatting arguments
        
        Returns:
            Formatted message string
        """
        if args:
            message = message % args
        
        # Remove leading newlines, preserving their count
        leading_newlines = len(message) - len(message.lstrip('\n'))
        message = message.lstrip('\n')
        
        return '\n' * leading_newlines + message

    def _log(self, level, message, *args):
        """
        Log message with specified level
        
        Args:
            level: Logging level (info, success, warn, error)
            message: Message to log
            *args: Optional formatting arguments
        """
        # Get icon color, symbol, and text color for the level
        icon_color, symbol, text_color = self.LEVELS.get(level, (Fore.WHITE, '•', Fore.WHITE))
        
        # Format message
        formatted_message = self._format_message(message, *args)
        
        # Generate timestamp if enabled
        timestamp = f"{icon_color}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL} " if self.use_timestamp else ""
        
        # Construct and print log message
        log_message = f"{timestamp}[{icon_color}{symbol}{Style.RESET_ALL}] {text_color}{formatted_message}{Style.RESET_ALL}"
        print(log_message, file=self.stream)

    def info(self, message, *args):
        """Sky blue [*] for general information"""
        self._log('info', message, *args)
    
    def info_repo(self, message, *args):
        """Sky blue [*] for general information"""
        self._log('info_repo', message, *args)

    def info_branch(self, message, *args):
        """Sky blue [*] for general information"""
        self._log('info_branch', message, *args)

    def success(self, message, *args):
        """Green [+] for successful operations"""
        self._log('success', message, *args)

    def success_report(self, message, *args):
        """Green [>] for successful operations"""
        self._log('success_report', message, *args)

    def warn(self, message, *args):
        """Yellow [!] for warnings"""
        self._log('warn', message, *args)

    def error(self, message, *args):
        """Red [-] for errors"""
        self._log('error', message, *args)

log = Logger()

class CSVReportGenerator:
    def __init__(self, 
                 project, 
                 organization, 
                 search_params=None):
        """
        Initialize the CSV Report Generator
        
        :param project: Azure DevOps project name
        :param organization: Azure DevOps organization name
        :param search_params: Dictionary of search parameters
        """
        self.project = project
        self.organization = organization
        self.search_params = search_params or {}
    
    def generate_report(self, results, report_type, output_filename=None):
        """
        Generate and save a CSV report
        
        :param results: List of search or commit results
        :param report_type: Type of report ('search' or 'commits')
        :param output_filename: Optional custom filename
        :return: Path to the saved CSV file
        """
        # If no filename provided, generate a default one
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"Azure_DevOops_{report_type}_report_{timestamp}.csv"
        
        # Create CSV content
        csv_content = self._create_csv_content(results, report_type)
        
        # Save to file
        with open(output_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            csvfile.write(csv_content)
        
        print()
        log.success_report(f"CSV report generated: {output_filename}")
        return output_filename
    
    def _create_csv_content(self, results, report_type):
        """
        Create CSV content based on report type
        
        :param results: List of results
        :param report_type: Type of report
        :return: CSV content as a string
        """
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer, quoting=csv.QUOTE_MINIMAL)
        
        # Report Header
        csv_writer.writerow([f"Azure DevOops {report_type.capitalize()} Report"])
        csv_writer.writerow([])
        
        # Search Parameters
        csv_writer.writerow(["Search Parameters"])
        csv_writer.writerow(["Project", self.project])
        csv_writer.writerow(["Organization", self.organization])
        
        # Detailed Search Configuration
        for key, value in self.search_params.items():
            csv_writer.writerow([key, str(value)])
        
        csv_writer.writerow(["Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        csv_writer.writerow([])
        
        # Results Header and Data
        if report_type == 'commits':
            csv_writer.writerow([
                "Repository",
                "Commit ID", 
                "Author", 
                "Date", 
                "Changed Files",
                "Commit Message"
            ])

            for result in results:
                author = result.get('author', '') + f" <{result['email']}>"
                csv_writer.writerow([
                    result.get('repository', 'N/A'),
                    result.get('commit_id', ''),
                    author,
                    result.get('date', ''),
                    '; '.join([change.get('item', {}).get('path', 'N/A') for change in result.get('changes', [])]),
                    result.get('message', '').replace('\n', ' ')
                ])
        
        elif report_type == 'search':
            csv_writer.writerow([
                "Repository", 
                "Branch", 
                "File", 
                "Line", 
                "Match"
            ])
                            
            for branch_result in results:
                repository = branch_result.get('repository', 'N/A')
                branch_name = branch_result.get('branch', 'Unknown Branch')

                for result in branch_result.get('results', []):
                    file_path = result.get('file_path', 'Unknown File')

                    for match in result.get('matches', []):
                        line_number = match.get('match_line_number', 'N/A')
                        
                        # Find the actual matched line
                        matched_line = next(
                            (ctx['line'] for ctx in match.get('context', []) if ctx.get('is_match')), 
                            'No match found'
                        )

                        csv_writer.writerow([
                            repository,
                            branch_name,
                            file_path,
                            line_number,
                            matched_line.replace('\n', ' ')
                        ])
        
        return csv_buffer.getvalue()

class HTMLReporter:
    def __init__(self, project, organization, search_params):
        """
        Initialize HTML reporter with search context
        
        Args:
            project: Azure DevOps project name
            organization: Organization name
            search_params: Dictionary of search parameters
        """
        self.project = project
        self.organization = organization
        self.search_params = search_params
        self.unique_id = str(uuid.uuid4())[:8]

    def _generate_filename(self, report_type='search'):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = f"Azure_DevOops_{report_type}_report_{timestamp}.html"
        
        return filename

    def generate_report(self, results, report_type='search'):
        """
        Generate HTML report for search or commit results
        """
        
        html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Azure DevOops {report_type.capitalize()} Report</title>
                <style>
                    :root {{
                        --bg-primary: #1E1E1E;
                        --bg-secondary: #252526;
                        --text-primary: #D4D4D4;
                        --text-secondary: #9CDCFE;
                        --border-color: #3C3C3C;
                        --highlight-color: #569CD6;
                        --hover-color: rgba(86, 156, 214, 0.2);
                    }}
                    
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background-color: var(--bg-primary);
                        color: var(--text-primary);
                        line-height: 1.6;
                        padding: 20px;
                        margin: 0;
                        transition: background-color 0.3s, color 0.3s;
                    }}
                    
                    body.light-theme {{
                        --bg-primary: #FFFFFF;
                        --bg-secondary: #F4F4F4;
                        --text-primary: #333333;
                        --text-secondary: #0078D4;
                        --border-color: #CCCCCC;
                        --highlight-color: #0078D4;
                        --hover-color: rgba(0, 120, 212, 0.1);
                    }}
                    
                    .container {{
                        max-width: 1600px;
                        margin: 0 auto;
                        background-color: var(--bg-secondary);
                        padding: 20px;
                        border-radius: 5px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    }}
                    
                    .theme-toggle {{
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        z-index: 1000;
                        transition: transform 0.3s;
                    }}
                    
                    .theme-toggle:hover {{
                        transform: scale(1.1);
                    }}
                    
                    h1, h2 {{
                        color: var(--highlight-color);
                        border-bottom: 1px solid var(--border-color);
                        padding-bottom: 10px;
                    }}
                    
                    .table-container {{
                        max-width: 100%;
                        overflow-x: auto;
                        position: relative;
                    }}
                    
                    table {{
                        width: 100%;
                        border-collapse: separate;
                        border-spacing: 0;
                        margin-bottom: 20px;
                        min-width: 800px;
                    }}
                    
                    th, td {{
                        border: 1px solid var(--border-color);
                        padding: 12px;
                        text-align: left;
                        position: relative;
                        transition: background-color 0.2s;
                    }}
                    
                    th {{
                        background-color: var(--bg-primary);
                        color: var(--text-secondary);
                        position: sticky;
                        top: 0;
                        z-index: 10;
                        cursor: pointer;
                    }}
                    
                    th:hover {{
                        background-color: var(--highlight-color);
                        color: var(--text-primary);
                    }}
                    
                    tr:hover {{
                        background-color: var(--hover-color);
                    }}
                    
                    .sortable-header {{
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                    }}
                    
                    .sort-icon {{
                        margin-left: 5px;
                        opacity: 0.5;
                    }}
                    
                    .sort-icon.active {{
                        opacity: 1;
                    }}
                    
                    .match-cell {{
                        max-width: 300px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                    }}
                    
                    .match-expand {{
                        cursor: pointer;
                        color: var(--highlight-color);
                        text-decoration: underline;
                        margin-top: 5px;
                    }}
                    
                    .match-content {{
                        display: none;
                        background-color: var(--bg-primary);
                        padding: 10px;
                        margin-top: 10px;
                        max-height: 300px;
                        overflow: auto;
                        white-space: pre-wrap;
                    }}

                    /* Column Resizing Styles */
                    .column-resizer {{
                        position: absolute;
                        right: -5px;
                        top: 0;
                        bottom: 0;
                        width: 10px;
                        cursor: col-resize;
                        z-index: 100;
                    }}

                    .column-resizer:hover {{
                        background-color: var(--highlight-color);
                    }}

                    .resizing {{
                        user-select: none;
                        cursor: col-resize !important;
                    }}

                    .column-resize-tip {{
                        margin: 10px 0;
                        padding: 10px;
                        background-color: var(--hover-color);
                        border-radius: 5px;
                        text-align: center;
                    }}
                    
                    @media (max-width: 768px) {{
                        table {{
                            font-size: 12px;
                        }}
                        
                        th, td {{
                            padding: 8px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <button class="theme-toggle" onclick="toggleTheme()">🌙</button>
                
                <div class="container">
                    <center><h1>Azure DevOops {report_type.capitalize()} Report</h1></center>
                    
                    <div class="metadata">
                        <h2>Search Parameters</h2>
                        <strong>Organization: </strong>{html.escape(self.organization)}<br>
                        <strong>Project: </strong>{html.escape(self.project)}<br>
                        {self._generate_search_params_list()}
                        <strong>Timestamp: </strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    </div>

                    <h2>Results</h2>
                    <div class="table-container">
                        {self._generate_results_table(results, report_type)}
                    </div>
                </div>

                <script>
                function toggleTheme() {{
                    document.body.classList.toggle('light-theme');
                    localStorage.setItem('theme', document.body.classList.contains('light-theme') ? 'light' : 'dark');
                    updateThemeIcon();
                }}

                function updateThemeIcon() {{
                    const themeToggle = document.querySelector('.theme-toggle');
                    themeToggle.textContent = document.body.classList.contains('light-theme') ? '☀️' : '🌙';
                }}

                function setupColumnResizing() {{
                    const table = document.querySelector('table');
                    const headers = table.querySelectorAll('thead th');

                    headers.forEach((header, index) => {{
                        // Create resizer element
                        const resizer = document.createElement('div');
                        resizer.classList.add('column-resizer');
                        header.style.position = 'relative';
                        header.appendChild(resizer);

                        let isResizing = false;
                        let startX, startWidth;

                        resizer.addEventListener('mousedown', (e) => {{
                            e.preventDefault();
                            isResizing = true;
                            startX = e.pageX;
                            startWidth = header.offsetWidth;
                            document.body.classList.add('resizing');

                            document.addEventListener('mousemove', handleMouseMove);
                            document.addEventListener('mouseup', handleMouseUp);
                        }});

                        function handleMouseMove(e) {{
                            if (!isResizing) return;

                            const dx = e.pageX - startX;
                            const newWidth = startWidth + dx;

                            // Ensure column doesn't get too small
                            if (newWidth > 50) {{
                                header.style.width = `${{newWidth}}px`;

                                // Update corresponding column cells
                                const columnIndex = Array.from(headers).indexOf(header);
                                const columnCells = table.querySelectorAll(`tr td:nth-child(${{columnIndex + 1}}), tr th:nth-child(${{columnIndex + 1}})`);
                                columnCells.forEach(cell => {{
                                    cell.style.width = `${{newWidth}}px`;
                                }});
                            }}
                        }}

                        function handleMouseUp() {{
                            isResizing = false;
                            document.body.classList.remove('resizing');
                            document.removeEventListener('mousemove', handleMouseMove);
                            document.removeEventListener('mouseup', handleMouseUp);
                        }}
                    }});
                }}

                function sortTable(columnIndex, isNumeric = false) {{
                    const table = document.querySelector('table');
                    const tbody = table.querySelector('tbody');
                    const rows = Array.from(tbody.querySelectorAll('tr'));
                    const sortIcon = document.querySelectorAll('.sort-icon')[columnIndex];
                    const currentSortDirection = sortIcon.dataset.sortDirection || 'asc';

                    // Remove active class from all sort icons
                    document.querySelectorAll('.sort-icon').forEach(icon => {{
                        icon.classList.remove('active');
                        icon.textContent = '⬍';
                    }});

                    // Set current sort icon
                    sortIcon.classList.add('active');

                    const sortedRows = rows.sort((a, b) => {{
                        const aColText = a.querySelectorAll('td')[columnIndex].textContent.trim();
                        const bColText = b.querySelectorAll('td')[columnIndex].textContent.trim();

                        if (isNumeric) {{
                            return currentSortDirection === 'asc' 
                                ? parseFloat(aColText) - parseFloat(bColText)
                                : parseFloat(bColText) - parseFloat(aColText);
                        }} else {{
                            return currentSortDirection === 'asc'
                                ? aColText.localeCompare(bColText)
                                : bColText.localeCompare(aColText);
                        }}
                    }});

                    // Update sort direction
                    sortIcon.dataset.sortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
                    sortIcon.textContent = currentSortDirection === 'asc' ? '▲' : '▼';

                    // Reinsert sorted rows
                    sortedRows.forEach(row => tbody.appendChild(row));
                }}

                function setupMatchExpansion() {{
                    const matchCells = document.querySelectorAll('.match-cell');
                    
                    matchCells.forEach(cell => {{
                        // Create expand button if full match exists
                        if (cell.dataset.fullMatch) {{
                            const expandBtn = document.createElement('div');
                            expandBtn.classList.add('match-expand');
                            expandBtn.textContent = 'View Full Match';
                            
                            const expandContent = document.createElement('pre');
                            expandContent.classList.add('match-content');
                            expandContent.textContent = cell.dataset.fullMatch;
                            
                            expandBtn.addEventListener('click', function() {{
                                expandContent.style.display = 
                                    expandContent.style.display === 'block' ? 'none' : 'block';
                                expandBtn.textContent = 
                                    expandContent.style.display === 'block' 
                                        ? 'Hide Full Match' 
                                        : 'View Full Match';
                            }});
                            
                            cell.appendChild(expandBtn);
                            cell.appendChild(expandContent);
                        }}
                    }});
                }}

                function setupSortableHeaders() {{
                    const headers = document.querySelectorAll('thead th');
                    headers.forEach((header, index) => {{
                        // Remove existing listeners
                        header.innerHTML = header.textContent;

                        const sortIcon = document.createElement('span');
                        sortIcon.classList.add('sort-icon');
                        sortIcon.textContent = '⬍';
                        
                        const headerContent = document.createElement('div');
                        headerContent.classList.add('sortable-header');
                        headerContent.innerHTML = header.innerHTML;
                        headerContent.appendChild(sortIcon);
                        
                        header.innerHTML = '';
                        header.appendChild(headerContent);
                        
                        header.addEventListener('click', () => {{
                            const isNumeric = header.classList.contains('numeric');
                            sortTable(index, isNumeric);
                        }});
                    }});
                }}

                document.addEventListener('DOMContentLoaded', () => {{
                    const savedTheme = localStorage.getItem('theme');
                    if (savedTheme === 'light') {{
                        document.body.classList.add('light-theme');
                    }}
                    
                    updateThemeIcon();
                    setupMatchExpansion();
                    setupSortableHeaders();
                    setupColumnResizing();
                }});
                </script>
            </body>
            </html>
        """
        
        # Generate filename and write HTML to current working directory
        filename = self._generate_filename(report_type)
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print()
        log.success_report(f"HTML report generated: {filename}")
        return filepath

    def _generate_search_params_list(self):
        """
        Generate an HTML list of all relevant search parameters
        """
        # Collect commit-specific parameters
        params = [
            # Existing search-related parameters
            ('Search Terms', self.search_params.get('search_terms', 'N/A')),
            ('Repositories', ', '.join(self.search_params.get('repos', ['All']))),
            
            # Commit-specific parameters
            ('Commit Search Terms', self.search_params.get('commit_terms', 'N/A')),
            ('Author Filter', self.search_params.get('author', 'None')),
            ('Date Range', self._format_date_range()),
            
            # Existing parameters
            ('Case Sensitive', self.search_params.get('case_sensitive', 'No')),
            ('Using Regex', self.search_params.get('regex', 'No')),
            ('Context Lines', self.search_params.get('context_lines', 0)),
            ('All Branches', self.search_params.get('all_branches', 'No')),
            ('Threading', 'Enabled' if self.search_params.get('use_threads', True) else 'Disabled')
        ]
        
        params_html = ""
        for key, value in params:
            # Skip empty or None values
            if value is None or value == 'N/A':
                continue
            
            # Convert complex types to strings for display
            if isinstance(value, (list, dict)):
                value = str(value)
            
            # Escape HTML and handle None values
            safe_value = html.escape(str(value)) if value is not None else 'N/A'
            
            params_html += f"""
            <strong>{html.escape(str(key))}:</strong> 
            <span class="long-text">{safe_value}</span>
            <br>
            """
        
        return params_html

    def _format_date_range(self):
        """
        Format date range for display
        """
        from_date = self.search_params.get('from_date')
        to_date = self.search_params.get('to_date')
        
        if from_date and to_date:
            return f"{from_date} to {to_date}"
        elif from_date:
            return f"From {from_date}"
        elif to_date:
            return f"Until {to_date}"
        else:
            return 'All dates'

    def _generate_results_table(self, results, report_type):
        """
        Generate an HTML table of search or commit results
        """
        if not results:
            return "<p>No results found.</p>"
        
        if report_type == 'search':
            return self._generate_search_results_table(results)
        elif report_type == 'commits':
            return self._generate_commit_results_table(results)
        else:
            return "<p>Invalid report type.</p>"

    def _generate_search_results_table(self, results):
        """
        Generate HTML table for search results with expandable match section
        """
        table_html = """
        <table>
            <thead>
                <tr>
                    <th>Repository</th>
                    <th>Branch</th>
                    <th>File</th>
                    <th>Line</th>
                    <th>Match</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for branch_result in results:
            repository_name = branch_result.get('repository', 'N/A')
            branch_name = branch_result.get('branch', 'Unknown Branch')
            
            for result in branch_result.get('results', []):
                file_path = result.get('file_path', 'Unknown File')
                
                for match in result.get('matches', []):
                    line_number = match.get('match_line_number', 'N/A')
                    
                    # Find the actual matched line and full context
                    matched_line = next(
                        (ctx['line'] for ctx in match.get('context', []) if ctx.get('is_match')), 
                        'No match found'
                    )
                    
                    # Collect full context for expandable view, without any markers
                    full_context = "\n".join([
                        ctx['line']
                        for ctx in match.get('context', [])
                    ])
                    
                    table_html += f"""
                    <tr>
                        <td>{html.escape(str(repository_name))}</td>
                        <td>{html.escape(branch_name)}</td>
                        <td>{html.escape(file_path)}</td>
                        <td>{line_number}</td>
                        <td class="match-cell" data-full-match="{html.escape(full_context)}">{html.escape(matched_line)}</td>
                    </tr>
                    """
        
        table_html += """
            </tbody>
        </table>
        """
        
        return table_html

    def _generate_commit_results_table(self, results):
        """
        Generate HTML table for commit search results
        """
        table_html = """
        <table>
            <thead>
                <tr>
                    <th>Repository</th>
                    <th>Commit ID</th>
                    <th>Author</th>
                    <th>Date</th>
                    <th>Changed Files</th>
                    <th>Commit Message</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for result in results:
            table_html += f"""
            <tr>
                <td>{html.escape(result.get('repository', 'N/A'))}</td>
                <td>{html.escape(result['commit_id'])}</td>
                <td>{html.escape(result['author'])} &lt;{html.escape(result['email'])}&gt;</td>
                <td>{html.escape(result['date'])}</td>
                <td>
                    <ul>
                        {"".join(f'<li>{html.escape(change.get("item", {}).get("path", "N/A"))}</li>' for change in result.get('changes', []))}
                    </ul>
                </td>
                <td class="match">{html.escape(result['message'])}</td>
            </tr>
            """
        
        table_html += """
            </tbody>
        </table>
        """
        
        return table_html

class AuthType(Enum):
    PAT = "pat"
    COOKIE = "cookie"

@dataclass
class AuthConfig:
    """Authentication configuration for Azure DevOps"""
    auth_type: AuthType
    credentials: str

class AzureDevOpsClient:
    def __init__(self, organization: str, auth_config: AuthConfig):
        """
        Initialize Azure DevOps client
        
        Args:
            organization: Azure DevOps organization name
            auth_config: Authentication configuration containing type and credentials
        """
        self.organization = organization
        self.base_url = f"https://dev.azure.com/{organization}"
        self.headers = self._get_auth_headers(auth_config)
        self.session = requests.Session()
        for key, value in self.headers.items():
            self.session.headers[key] = value

    def _get_auth_headers(self, auth_config: AuthConfig) -> Dict[str, str]:
        """Generate headers based on authentication type"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }
        
        if auth_config.auth_type == AuthType.COOKIE:
            headers['Cookie'] = f"AadAuthenticationSet=false; {auth_config.credentials}"
        else:  # AuthType.PAT
            token = f":{auth_config.credentials}"
            basic_auth = b64encode(token.encode('utf-8')).decode('utf-8')
            headers['Authorization'] = f'Basic {basic_auth}'
        
        return headers

    def get_repositories(self, project: str) -> List[Dict]:
        """Get all repositories in a project"""
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories?api-version=6.0"
            response = self.session.get(url, allow_redirects=False)
            
            if response.status_code in (301, 302, 303, 307, 308):
                raise ValueError("Authentication failed - redirected to login page. Please check your credentials.")
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                print(f"\nRaw Response Text (first 500 characters):")
                print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
                raise ValueError(f"Invalid JSON response (Status code: {response.status_code})")
            
            if response.status_code == 401:
                raise ValueError("Authentication failed. Please check your credentials.")
            elif response.status_code == 404:
                raise ValueError(f"Project '{project}' not found.")
            
            response.raise_for_status()
            return response_data.get('value', [])
            
        except requests.exceptions.RequestException as e:
            print(f"Error accessing Azure DevOps API: {str(e)}")
            raise

    def get_repository_branches(self, project: str, repository_id: str) -> List[Dict]:
        """Get all branches in a repository"""
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories/{repository_id}/refs"
            params = {
                "filter": "heads/",
                "api-version": "6.0"
            }
            response = self.session.get(url, params=params, allow_redirects=False)
            response.raise_for_status()
            return response.json().get('value', [])
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 404:
                return []
            print(f"Error fetching branches: {str(e)}")
            raise

    def get_repository_items(self, project: str, repository_id: str, path: str = "", branch: str = None) -> List[Dict]:
        """Get items in a repository at a specific path"""
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories/{repository_id}/items"
            params = {
                "scopePath": path,
                "recursionLevel": "OneLevel",
                "api-version": "6.0"
            }
            if branch:
                params.update({
                    "versionDescriptor.version": branch,
                    "versionDescriptor.versionType": "branch"
                })
                
            response = self.session.get(url, params=params, allow_redirects=False)
            response.raise_for_status()
            return response.json().get('value', [])
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 404:
                return []
            print(f"Error fetching repository items: {str(e)}")
            raise

    def get_file_content(self, project: str, repository_id: str, path: str, branch: str = None) -> Optional[str]:
        """Get the content of a file from the repository"""
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories/{repository_id}/items"
            params = {
                "path": path,
                "recursionLevel": "0",
                "includeContentMetadata": "true",
                "includeContent": "true",
                "resolveLfs": "true",
                "api-version": "6.0"
            }
            
            if branch:
                params.update({
                    "versionDescriptor.version": branch,
                    "versionDescriptor.versionType": "branch"
                })
            
            response = self.session.get(url, params=params, allow_redirects=False)
            response.raise_for_status()
            
            try:
                data = response.json()
                return data.get('content')
            except json.JSONDecodeError:
                return response.text
                
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 404:
                return None
            print(f"Error fetching file content: {str(e)}")
            return None

    def is_text_file(self, file_path: str) -> bool:
        """Determine if a file is likely to be text-based"""
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        text_extensions = {
            # Source Code
            '.txt', '.md', 
            '.py', 
            '.js', '.jsx', 
            '.ts', '.tsx',        
            '.java', 
            '.c', '.cpp', '.h', '.hpp', 
            '.cs',               
            '.go',                
            '.rb',                 
            '.php', 
            '.swift', 
            '.m', '.mm',            
            
            # Web Development
            '.html', '.htm', 
            '.css', '.scss', '.less', 
            '.xml', 
            '.json', 
            '.yml', '.yaml', 
            
            # Configuration/Scripting
            '.ini', 
            '.conf', 
            '.cfg', 
            '.sh', 
            '.bash', 
            '.bat', 
            '.cmd', 
            '.ps1', 
            '.pl',                
            '.sql', 
            '.config', 
            
            # Additional Extensions
            '.properties',
            '.toml',
            '.env',
            '.log',
        }
        
        conditions = [
            file_ext in text_extensions,
            
            filename.startswith('.'),
            
            filename.startswith('_'),

            filename.startswith('~'),

            filename.endswith(''),
            
            # mime type detection as a fallback
            mimetypes.guess_type(file_path)[0] is not None and 
            mimetypes.guess_type(file_path)[0].startswith('text/') or mimetypes in {
                'application/json', 'application/xml', 'application/javascript',
                'application/x-python-code', 'application/x-yaml'
            }
        ]
        
        return any(conditions)

    def print_repository_tree(self, project: str, repository_id: str, branch: str = None):
        """Print the tree structure for a specific repository"""
        visited_paths = set()

        def _print_tree(path: str = "", prefix: str = ""):
            if path in visited_paths:
                return
            visited_paths.add(path)
            
            items = self.get_repository_items(project, repository_id, path, branch)
            items = [item for item in items if item['path'] != path]
            items.sort(key=lambda x: (x.get('gitObjectType', '') != 'tree', x['path']))
            
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "
                
                item_name = item['path'].split('/')[-1]
                if not item_name and item['path'] == '/':
                    continue
                    
                print(f"{prefix}{current_prefix}{item_name}")
                
                if item.get('gitObjectType') == 'tree':
                    _print_tree(item['path'], prefix + next_prefix)

        print(".")
        _print_tree()

    def search_repository(self, project: str, repository_id: str, search_terms: List[str], 
                        branch: str = None, all_branches: bool = False, 
                        case_sensitive: bool = True, extensions: Set[str] = None,
                        context_lines: int = 0, use_regex: bool = False, 
                        use_threads: bool = True) -> List[Dict]:
        """
        Search for multiple strings in text files of a repository
        
        Args:
            project: Azure DevOps project name
            repository_id: ID of the repository to search
            search_terms: List of terms or regex patterns to search for
            branch: Specific branch to search (if not all_branches)
            all_branches: Flag to search across all branches
            case_sensitive: Whether search is case-sensitive
            extensions: Set of file extensions to include in search
            context_lines: Number of lines to show before and after match
            use_regex: Whether search terms are regex patterns
            use_threads: Whether to use ThreadPoolExecutor for searching (default True)
        
        Returns:
            List of search results, each containing branch and matching files
        """
        # If not searching all branches, search only the specified branch
        if not all_branches:
            return [self.search_branch(
                project, 
                repository_id, 
                branch, 
                search_terms, 
                case_sensitive, 
                extensions, 
                context_lines, 
                use_regex
            )]
        
        # Get all branches in the repository
        branches = self.get_repository_branches(project, repository_id)
        branch_names = [
            format_branch_name(b['name']) 
            for b in branches 
            if b['name'].startswith('refs/heads/')
        ]
        
        results = []
        # Create progress bar for branch-level search
        with tqdm(
            total=len(branch_names), 
            desc=colored("Searching Branches", "cyan"), 
            unit="branch", 
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            colour="green"
        ) as repo_progress:
            # Threaded or sequential search based on flag
            if use_threads:
                # Use thread pool to search branches concurrently
                with ThreadPoolExecutor(max_workers=5) as executor:
                    # Prepare search tasks for each branch
                    future_to_branch = {
                        executor.submit(
                            self.search_branch, 
                            project, 
                            repository_id, 
                            branch_name, 
                            search_terms, 
                            case_sensitive,
                            extensions,
                            context_lines,
                            use_regex
                        ): branch_name
                        for branch_name in branch_names
                    }
                    
                    # Process completed search tasks
                    for future in as_completed(future_to_branch):
                        try:
                            result = future.result()
                            # Update overall progress
                            repo_progress.update(1)
                            
                            # Only keep results with matches
                            if result['results']:
                                results.append(result)
                        except Exception as e:
                            # Log any errors during branch search
                            repo_progress.write(
                                colored(f"Error in branch {future_to_branch[future]}: {str(e)}", "red")
                            )
            else:
                # Sequential search
                for branch_name in branch_names:
                    try:
                        result = self.search_branch(
                            project, 
                            repository_id, 
                            branch_name, 
                            search_terms, 
                            case_sensitive,
                            extensions,
                            context_lines,
                            use_regex
                        )
                        # Update overall progress
                        repo_progress.update(1)
                        
                        # Only keep results with matches
                        if result['results']:
                            results.append(result)
                    except Exception as e:
                        # Log any errors during branch search
                        repo_progress.write(
                            colored(f"Error in branch {branch_name}: {str(e)}", "red")
                        )
        
        return results

    def search_branch(self, project: str, repository_id: str, branch: str, search_terms: List[str], 
                    case_sensitive: bool = True, extensions: Set[str] = None, 
                    context_lines: int = 0, use_regex: bool = False) -> Dict:
        """
        Search for terms in a specific branch
        
        Args:
            project: Azure DevOps project name
            repository_id: ID of the repository
            branch: Branch to search
            search_terms: List of terms or regex patterns to search for
            case_sensitive: Whether search is case-sensitive
            extensions: Set of file extensions to include in search
            context_lines: Number of lines to show before and after match
            use_regex: Whether search terms are regex patterns
        
        Returns:
            Dict containing branch name and list of matching files
        """
        results = []
        visited_paths = set()
        
        def compile_patterns(terms: List[str], case_sensitive: bool) -> List[re.Pattern]:
            """Compile search patterns with appropriate flags"""
            flags = 0 if case_sensitive else re.IGNORECASE
            patterns = []
            for term in terms:
                try:
                    # Use regex if specified, otherwise escape the term
                    pattern = re.compile(term if use_regex else re.escape(term), flags)
                    patterns.append(pattern)
                except re.error:
                    print(f"Warning: Invalid regex pattern '{term}', skipping...")
            return patterns

        def search_in_path(path: str = "", progress_bar=None):
            """Recursive search through repository paths"""
            if path in visited_paths:
                return
            visited_paths.add(path)
            
            try:
                # Get items in the current path
                items = self.get_repository_items(project, repository_id, path, branch)
                
                # Filter items based on extensions
                filtered_items = [
                    item for item in items 
                    if item['path'] != path and 
                    (not extensions or os.path.splitext(item['path'])[1].lower() in extensions)
                ]

                # Update progress bar total if possible
                if progress_bar is not None and filtered_items:
                    progress_bar.total = len(filtered_items)
                    progress_bar.refresh()

                # Search through filtered items
                for item in filtered_items:
                    # Recursively search directories
                    if item.get('gitObjectType') == 'tree':
                        search_in_path(item['path'], progress_bar)
                    
                    # Check if item is a text file
                    elif self.is_text_file(item['path']):
                        # Update progress bar description
                        if progress_bar:
                            progress_bar.set_description(colored(f"Searching: {item['path']}", 'cyan'))
                        
                        # Get file content
                        content = self.get_file_content(project, repository_id, item['path'], branch)
                        if content:
                            lines = content.splitlines()
                            patterns = compile_patterns(search_terms, case_sensitive)
                            line_matches = []
                            
                            # Search through lines
                            for i, line in enumerate(lines, 1):
                                for pattern in patterns:
                                    if pattern.search(line):
                                        # Collect context lines
                                        context_start = max(0, i - 1 - context_lines)
                                        context_end = min(len(lines), i + context_lines)
                                        context = []
                                        
                                        # Add lines before match
                                        if context_lines > 0:
                                            context.extend([
                                                {
                                                    'line_number': ctx_line_num + 1,
                                                    'line': lines[ctx_line_num].strip(),
                                                    'is_match': False
                                                }
                                                for ctx_line_num in range(context_start, i - 1)
                                            ])
                                        
                                        # Add matching line
                                        context.append({
                                            'line_number': i,
                                            'line': line.strip(),
                                            'is_match': True,
                                            'term': pattern.pattern
                                        })
                                        
                                        # Add lines after match
                                        if context_lines > 0:
                                            context.extend([
                                                {
                                                    'line_number': ctx_line_num + 1,
                                                    'line': lines[ctx_line_num].strip(),
                                                    'is_match': False
                                                }
                                                for ctx_line_num in range(i, context_end)
                                            ])
                                        
                                        line_matches.append({
                                            'match_line_number': i,
                                            'context': context
                                        })
                                        break  # Stop after first match
                            
                            # Store results if matches found
                            if line_matches:
                                results.append({
                                    'file_path': item['path'],
                                    'matches': line_matches
                                })
                    
                    # Update progress bar
                    if progress_bar:
                        try:
                            progress_bar.update(1)
                        except Exception:
                            pass

            except Exception as e:
                print(f"Error searching path {path}: {e}")

        try:
            # Create progress bar for branch search
            with tqdm(
                total=0,  # Will be updated dynamically
                desc=colored(f"Searching {branch}", "cyan"), 
                unit="file", 
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                colour="green",
                position=0,
                leave=False  # Remove progress bar after completion
            ) as progress_bar:
                search_in_path(progress_bar=progress_bar)
        except Exception as e:
            print(colored(f"Error searching branch {branch}: {e}", "red"))

        return {
            'branch': branch,
            'results': results
        }

        
    def get_commits(self, project: str, repository_id: str, branch: str = None, 
                   search_text: str = None, author: str = None, 
                   from_date: str = None, to_date: str = None) -> List[Dict]:
        """
        Get commits from a repository with optional filtering
        
        Args:
            project: Project name
            repository_id: Repository ID
            branch: Branch name (optional)
            search_text: Text to search in commit messages
            author: Author email or display name to filter by
            from_date: Start date in ISO format (YYYY-MM-DD)
            to_date: End date in ISO format (YYYY-MM-DD)
        """
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories/{repository_id}/commits"
            params = {
                "api-version": "6.0",
                "$top": 1000  # Adjust as needed
            }

            # Add optional filters
            if branch:
                params["searchCriteria.itemVersion.version"] = branch
            if search_text:
                params["searchCriteria.itemVersion.version"] = search_text
            if author:
                params["searchCriteria.author"] = author
            if from_date:
                params["searchCriteria.fromDate"] = f"{from_date}T00:00:00Z"
            if to_date:
                params["searchCriteria.toDate"] = f"{to_date}T23:59:59Z"

            response = self.session.get(url, params=params, allow_redirects=False)
            response.raise_for_status()
            return response.json().get('value', [])

        except requests.exceptions.RequestException as e:
            print(f"Error fetching commits: {str(e)}")
            return []

    def get_commit_changes(self, project: str, repository_id: str, commit_id: str) -> List[Dict]:
        """Get the changes (files modified) in a specific commit"""
        try:
            url = f"{self.base_url}/{project}/_apis/git/repositories/{repository_id}/commits/{commit_id}/changes"
            params = {"api-version": "6.0"}
            
            response = self.session.get(url, params=params, allow_redirects=False)
            response.raise_for_status()
            return response.json().get('changes', [])

        except requests.exceptions.RequestException as e:
            print(f"Error fetching commit changes: {str(e)}")
            return []

    def search_commit_history(self, project: str, repository_id: str, search_terms: List[str],
                            branch: str = None, author: str = None,
                            from_date: str = None, to_date: str = None,
                            case_sensitive: bool = True, use_regex: bool = False) -> List[Dict]:
        """
        Search through commit history for specific terms
        
        Args:
            project: Project name
            repository_id: Repository ID
            search_terms: List of terms to search for
            branch: Branch name (optional)
            author: Author to filter by (optional)
            from_date: Start date in ISO format (optional)
            to_date: End date in ISO format (optional)
            case_sensitive: Whether to perform case-sensitive search
            use_regex: Whether to treat search terms as regular expressions
        """
        commits = self.get_commits(project, repository_id, branch, author=author,
                                 from_date=from_date, to_date=to_date)
        #print(commits)

        def compile_patterns(terms: List[str], case_sensitive: bool) -> List[re.Pattern]:
            flags = 0 if case_sensitive else re.IGNORECASE
            patterns = []
            for term in terms:
                if use_regex:
                    try:
                        patterns.append(re.compile(term, flags))
                    except re.error:
                        print(f"Warning: Invalid regex pattern '{term}', skipping...")
                else:
                    patterns.append(re.compile(re.escape(term), flags))
            return patterns

        patterns = compile_patterns(search_terms, case_sensitive)
        results = []

        for commit in commits:
            message = commit.get('comment', '')
            for pattern in patterns:
                if pattern.search(message):
                    # Get the changes for this commit
                    changes = self.get_commit_changes(project, repository_id, commit['commitId'])

                    #for i in changes:
                        #print(i)
                    
                    # Format the commit date
                    commit_date = datetime.strptime(
                        commit['author']['date'], 
                        '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=timezone.utc)
                    
                    results.append({
                        'commit_id': commit['commitId'],
                        'author': commit['author']['name'],
                        'email': commit['author']['email'],
                        'date': commit_date.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        'message': message,
                        'changes': changes
                    })
                    break  # Found a match, no need to check other patterns

        return results

def highlight_terms(text: str, terms: List[str], case_sensitive: bool = True, use_regex: bool = False) -> str:
    """Highlight search terms in green in the given text"""
    def compile_patterns(terms: List[str], case_sensitive: bool) -> List[re.Pattern]:
        flags = 0 if case_sensitive else re.IGNORECASE
        patterns = []
        for term in terms:
            if use_regex:
                try:
                    patterns.append(re.compile(term, flags))
                except re.error:
                    continue
            else:
                patterns.append(re.compile(re.escape(term), flags))
        return patterns

    # Compile patterns first
    patterns = compile_patterns(terms, case_sensitive)
    result = text
    
    # Sort patterns by length (longest first) to handle overlapping matches
    patterns.sort(key=lambda p: len(p.pattern), reverse=True)
    
    for pattern in patterns:
        # Use re.finditer to get all matches and their positions
        pos = 0
        while True:
            match = pattern.search(result, pos)
            if not match:
                break
            start, end = match.span()
            matched_text = result[start:end]
            result = result[:start] + colored(matched_text, 'green') + result[end:]
            pos = start + len(colored(matched_text, 'green'))
    
    return result

def determine_auth_type(credential: str) -> AuthConfig:
    """Determine authentication type based on credential format"""
    return AuthConfig(
        AuthType.COOKIE if credential.lower().startswith("userauthentication=") else AuthType.PAT,
        credential
    )

def format_branch_name(name: str) -> str:
    """Format branch name by removing refs/heads/ prefix"""
    return name.replace('refs/heads/', '')

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  devoops.py -o myorg -p myproject -cf cred
  devoops.py -o myorg -p myproject -cf cred --repos repo1,repo2
  devoops.py -o myorg -p myproject -cf cred --repos repo1 --search "TODO,FIXME" --all-branches
  devoops.py -o myorg -p myproject -cf cred --search "password" --lines 3 --exclude-repos test-repo,temp-repo
  devoops.py -o myorg -p myproject -cf cred --commits "secret" --author dev@target.com --from-date 2025-12-09
  devoops.py -o myorg -p myproject -cf cred --repos repo1 --search "<REGEX PATTERN>" --regex --case-insensitive --only-ext ".ps1,.json"

Regex:
  Client ID      [0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}
  Client Secret  [a-zA-Z0-9~.\-_]{40}
  Access Token   eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+ 
  Refresh Token  0.AY[A-Za-z0-9-_.+/=]*
""")
    
    # essential
    parser.add_argument('-o', '--organization', 
                       required=True,
                       help='Azure DevOps organization name')
    
    parser.add_argument('-p', '--project',
                       required=True,
                       help='Azure DevOps project name')
    
    # creds 
    cred_group = parser.add_mutually_exclusive_group(required=True)
    cred_group.add_argument('-c', '--credential',
                           help='Raw authentication credential (PAT token or UserAuthentication=cookie)')
    
    cred_group.add_argument('-cf', '--cred-file',
                           help='Path to file containing authentication credential')
    
    # search + commit settings
    parser.add_argument('--repos',
                       help='Comma-separated list of repository names to display OR search (displays ALL if not specified)')
    
    parser.add_argument('--list-repos',
                       action='store_true',
                       help='Only list repository names without showing contents')
    
    parser.add_argument('--list-contents', 
                    action='store_true', 
                    help='List contents of repositories (--repos REQUIRED)')

    parser.add_argument('--search',
                       help='Comma-separated list of file search strings, raw regex patterns (--regex REQUIRED), or YML file')
    
    parser.add_argument('--branches',
                       help='Comma-separated list of branch names to display OR search (displays ALL if not specified)')

    parser.add_argument('--all-branches',
                       action='store_true',
                       help='List files or search across ALL branches')
    
    parser.add_argument('--case-insensitive',
                       action='store_true',
                       help='Perform case-insensitive search')
                       
    parser.add_argument('--only-ext',
                       help='Comma-separated list of file extensions to search (e.g., ".py,.js,.ps1")')
    
    parser.add_argument('--regex',
                       action='store_true',
                       help='Treat search strings (--search REQUIRED) as regular expressions')
    
    parser.add_argument('--lines',
                       type=int,
                       default=0,
                       help='Number of lines to show before and after matches for context')
    
    parser.add_argument('--exclude-repos',
                       help='Comma-separated list of repository names to exclude from search')

    parser.add_argument('--commits',
                       help='Comma-separated list of commit search strings, raw regex patterns (--regex REQUIRED), or YML file')
    
    parser.add_argument('--list-commits', 
                    action='store_true', 
                    help='List commits for specified repositories (--repos REQUIRED)')
    
    parser.add_argument('--author',
                       help='Filter commits by author (email or display name)')
    
    parser.add_argument('--from-date',
                       help='Search commits from this date (YYYY-MM-DD)')
    
    parser.add_argument('--to-date',
                       help='Search commits until this date (YYYY-MM-DD)')

    parser.add_argument('--no-threads',
                       action='store_true',
                       help='Disable multi-threaded branch searching')
    
    # report
    parser.add_argument('--html-report', 
                        action='store_true', 
                        help='Generate an HTML report')

    parser.add_argument('--csv-report', 
                        action='store_true', 
                        help='Generate an CSV report')

    return parser.parse_args()


def get_credential_from_args(args) -> str:
    """Get credential from either command line argument or file"""
    if args.credential:
        return args.credential
    elif args.cred_file:
        try:
            with open(args.cred_file, 'r', encoding='utf-8') as f:
                credential = f.read().strip()
                if not credential:
                    raise ValueError(f"Credential file '{args.cred_file}' is empty")
                return credential
        except FileNotFoundError:
            raise ValueError(f"Credential file '{args.cred_file}' not found")
        except Exception as e:
            raise ValueError(f"Error reading credential file '{args.cred_file}': {str(e)}")
    else:
        raise ValueError("Either --credential or --cred-file must be provided")


def load_regex_patterns(yaml_file):
    """
    Load regex patterns from a YAML file
    
    Args:
        yaml_file (str): Path to the YAML file containing patterns
    
    Returns:
        List[str]: Extracted regex patterns
    """
    try:
        import yaml
        
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        if not data or 'patterns' not in data:
            log.error(f"No patterns found in {yaml_file}")
            return []
        
        patterns = []
        for pattern_entry in data.get('patterns', []):
            if isinstance(pattern_entry, dict) and 'pattern' in pattern_entry:
                pattern_info = pattern_entry['pattern']
                
                if isinstance(pattern_info, dict):
                    regex = pattern_info.get('regex')
                elif isinstance(pattern_info, str):
                    regex = pattern_info
                else:
                    continue
                
                if regex:
                    patterns.append(regex)
        
        return patterns
    
    except ImportError:
        log.error("PyYAML library is required to read YAML files. Install with: pip install pyyaml")
        return []
    except FileNotFoundError:
        log.error(f"Regex pattern file not found: {yaml_file}")
        return []
    except yaml.YAMLError as e:
        log.error(f"Error parsing YAML file: {e}")
        return []

def is_yaml_file(path):
    """
    Check if the given path is a YAML file
    
    Args:
        path (str): File path to check
    
    Returns:
        bool: True if file exists and has .yml or .yaml extension
    """
    import os
    return (
        os.path.isfile(path) and 
        path.lower().endswith(('.yml', '.yaml'))
    )

def main():
    args = parse_arguments()

    # Get credential from either CLI argument or file
    try:
        credential = get_credential_from_args(args)
        auth_config = determine_auth_type(credential)
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

    # Process file extensions if provided
    extensions = None
    if args.only_ext:
        extensions = {ext.strip().lower() for ext in args.only_ext.split(',')}
        if not all(ext.startswith('.') for ext in extensions):
            log.error("Error: File extensions must start with a dot (e.g., '.py')")
            sys.exit(1)
    
    try:
        client = AzureDevOpsClient(args.organization, auth_config)
        
        # Step 1: Get all repositories in the project
        repos = client.get_repositories(args.project)
        if not repos:
            log.error(f"No repositories found in project '{args.project}'")
            return
        
        # Handle branch filtering
        specified_branches = set()
        
        if args.branches:
            specified_branches = {name.strip() for name in args.branches.split(',')}

        # Validate branch names if specified
        if specified_branches:
            log.info(f"Filtering for branches: {', '.join(specified_branches)}")

        # Step 2: Handle --list-repos flag
        if args.list_repos:
            log.info(f"Repositories in project '{args.project}':")
            for repo in repos:
                # Print repository name
                print(f"  - {repo['name']}")
                
                # Fetch branches for this repository
                try:
                    branches = client.get_repository_branches(args.project, repo['id'])
                    
                    # Filter and format branch names
                    branch_list = [
                        format_branch_name(branch['name'])
                        for branch in branches
                        if branch['name'].startswith('refs/heads/')
                    ]
                    
                    # Apply branch filtering
                    if specified_branches:
                        branch_list = [
                            branch for branch in branch_list 
                            if branch in specified_branches
                        ]
                    
                    # Sort and display branches
                    for branch in sorted(branch_list):
                        print(f"    * {branch}")
                        
                except requests.exceptions.RequestException as e:
                    log.error(f"    ! Error fetching branches: {str(e)}")
            
            return

        
        # Step 3: Handle repository filtering
        excluded_repos = set()
        if args.exclude_repos:
            excluded_repos = {name.strip() for name in args.exclude_repos.split(',')}
        
        if args.repos:
            requested_repos = {name.strip() for name in args.repos.split(',')}
            repos = [repo for repo in repos if repo['name'] in requested_repos]
        
        # Step 3.1: Apply exclusions
        repos = [repo for repo in repos if repo['name'] not in excluded_repos]
            
        if not repos:
            log.warn(f"No matching repositories found after filtering. Available repositories:")
            for repo in client.get_repositories(args.project):
                if repo['name'] not in excluded_repos:
                    print(f"  - {repo['name']}")
            return

        # Step 4: Process each repository
        all_search_results = []
        all_commit_results = []

        for repo in repos:
            print()
            log.info_repo(f"Repository: {repo['name']}")
            default_branch = repo.get('defaultBranch', 'N/A')
            log.info(f"Default branch: {default_branch}")
            
            # Step 4.1: Get branch information
            try:
                branches = client.get_repository_branches(args.project, repo['id'])
                branch_list = [
                    format_branch_name(branch['name'])
                    for branch in branches
                    if branch['name'].startswith('refs/heads/')
                ]
                
                # Apply branch filtering if --branches is specified
                if args.branches:
                    branch_list = [
                        branch for branch in branch_list 
                        if branch in specified_branches
                    ]
                
                # Display branches based on --all-branches flag
                if args.all_branches:
                    log.info("Branches:")
                    for branch in sorted(branch_list):
                        print(f" - {branch}")
                else:
                    other_branches = [
                        branch for branch in branch_list
                        if branch != format_branch_name(default_branch)
                    ]
                    if other_branches:
                        log.info("Other branches:")
                        for branch in sorted(other_branches):
                            print(f" - {branch}")
                            
            except requests.exceptions.RequestException as e:
                log.error(f"Error fetching branches: {str(e)}")
                continue

            # STEP 4.1.2 yml file processing checks
            if args.search and is_yaml_file(args.search):
                log.info(f"Loading search patterns from YAML file: {args.search}")
                search_terms = load_regex_patterns(args.search)
                if not search_terms:
                    log.error("No patterns found in search YAML file. Exiting.")
                    sys.exit(1)
                #args.search = ','.join(search_terms) - overpopulates the search terms field in report when loading from yml
                args.regex = True
            elif args.search:
                search_terms = [term.strip() for term in args.search.split(',')]
                log.info(f"Searching for patterns: {', '.join(search_terms)}")
            else:
                search_terms = []
            
            if args.commits and is_yaml_file(args.commits):
                log.info(f"Loading commit search patterns from YAML file: {args.commits}")
                commit_terms = load_regex_patterns(args.commits)
                if not commit_terms:
                    log.error("No patterns found in commits YAML file. Exiting.")
                    sys.exit(1)
                args.commits = ','.join(commit_terms)
                args.regex = True
            elif args.commits:
                commit_terms = [term.strip() for term in args.commits.split(',')]
                log.info(f"Searching for patterns: {', '.join(commit_terms)}")
            else:
                commit_terms = []

            # Step 4.2: Handle commit history search if --commits is specified
            if args.commits:
                search_terms = [term.strip() for term in args.commits.split(',')]
                log.info(f"Searching commit history for terms: {', '.join(search_terms)}")
                if args.regex:
                    log.info("Using regex patterns")
                if not args.regex:
                    log.info("No regex patterns")
                if args.case_insensitive:
                    log.info("Case-insensitive search")
                if args.author:
                    log.info(f"Filtering by author: {args.author}")
                if args.from_date or args.to_date:
                    date_range = f"from {args.from_date or 'beginning'} to {args.to_date or 'now'}"
                    log.info(f"Date range: {date_range}")

                try:
                    results = client.search_commit_history(
                        args.project,
                        repo['id'],
                        search_terms,
                        branch=format_branch_name(default_branch) if default_branch != 'N/A' else None,
                        author=args.author,
                        from_date=args.from_date,
                        to_date=args.to_date,
                        case_sensitive=not args.case_insensitive,
                        use_regex=args.regex
                    )

                    if results:
                        log.success(f"FOUND {len(results)} matching commits:")
                        for result in results:
                            result['repository'] = repo['name']

                            print("\n" + "-" * 80)
                            print(f"Commit: {result['commit_id']}")
                            print(f"Author: {result['author']} <{result['email']}>")
                            print(f"Date: {result['date']}")
                            print("\nMessage:")
                            highlighted_message = highlight_terms(
                                result['message'],
                                search_terms,
                                case_sensitive=not args.case_insensitive,
                                use_regex=args.regex
                            )
                            print(highlighted_message)
                            
                            if result['changes']:
                                print("\nChanged files:")
                                for change in result['changes']:
                                    change_type = change.get('changeType', 'modified')
                                    item = change.get('item', {})
                                    path = item.get('path', 'N/A')
                                    print(f"  {change_type}: {path}")
                        
                        all_commit_results.extend(results)

                    else:
                        log.warn("No matching commits found")

                except requests.exceptions.RequestException as e:
                    log.error(f"Error searching commit history: {str(e)}")
                    continue

            # Step 4.3: Handle file content search if --search is specified
            elif args.search:
                #search_terms = [term.strip() for term in args.search.split(',')]
                #log.info(f"Searching for terms: {', '.join(search_terms)}")
                
                if args.regex:
                    log.info("Using regex patterns")
                if not args.regex:
                    log.info("No regex patterns")
                if args.case_insensitive:
                    log.info("Case-insensitive search")
                if extensions:
                    log.info(f"File extensions: {', '.join(sorted(extensions))}")
                if args.lines > 0:
                    log.info(f"Showing {args.lines} lines of context before and after matches")
                
                try:
                    branch_to_search = None
                    if args.branches:
                        branch_to_search = next(iter(specified_branches))
                    else:
                        branch_to_search = format_branch_name(default_branch) if default_branch != 'N/A' else None

                    results = client.search_repository(
                        args.project, 
                        repo['id'], 
                        search_terms,
                        branch=branch_to_search,
                        all_branches=args.all_branches,
                        case_sensitive=not args.case_insensitive,
                        extensions=extensions,
                        context_lines=args.lines,
                        use_regex=args.regex,
                        use_threads=not args.no_threads
                    )
                    
                    if results:
                        branches_with_matches = [br for br in results if br['results']]
                        if branches_with_matches:
                            consolidated_results = []
                            seen_files = set()

                            for branch_result in branches_with_matches:
                                branch_result['repository'] = repo['name']  # Add repository name
                                branch_name = branch_result['branch']
                                branch_results = branch_result['results']
                                
                                # Consolidate unique results across branches
                                for result in branch_results:
                                    # Create a unique identifier for the result
                                    result_key = (repo['name'], branch_name, result['file_path'])
                                    
                                    if result_key not in seen_files:
                                        seen_files.add(result_key)
                                        
                                        # Create a copy to avoid modifying original results
                                        consolidated_result = {
                                            'repository': repo['name'],
                                            'branch': branch_name,
                                            'results': [result]
                                        }
                                        consolidated_results.append(consolidated_result)
                                        
                                log.info_branch(f"Branch: {branch_name}")
                                log.success(f"FOUND {len(consolidated_results)} unique matching files!!!")
                                
                                # Display results (keeping existing display logic)
                                for unique_result in consolidated_results:
                                    result = unique_result['results'][0]
                                    log.success(f"File: {result['file_path']}")
                                    for match_group in result['matches']:
                                        log.success(f"MATCH at line {match_group['match_line_number']}:")
                                        for ctx in match_group['context']:
                                            highlighted_line = highlight_terms(
                                                ctx['line'],
                                                search_terms,
                                                case_sensitive=not args.case_insensitive,
                                                use_regex=args.regex
                                            ) if ctx['is_match'] else ctx['line']
                                            print(f"{highlighted_line}")
                            
                            # Extend with consolidated results
                            all_search_results.extend(consolidated_results)

                        else:
                            log.warn("NO matches found in any branch :(")
                    else:
                        log.warn("NO matches found in any branch :(")
                        
                except requests.exceptions.RequestException as e:
                    log.error(f"Error during search: {str(e)}")
                    continue

        # Generate final reports AFTER processing all repositories
        if args.commits and all_commit_results:
            if args.html_report:
                html_reporter = HTMLReporter(
                    project=args.project, 
                    organization=args.organization, 
                    search_params={
                        'search_terms': args.commits,
                        'repos': [repo['name'] for repo in repos],
                        'case_sensitive': not args.case_insensitive,
                        'regex': args.regex,
                        'author': args.author,
                        'from_date': args.from_date,
                        'to_date': args.to_date,
                        'context_lines': args.lines,
                        'all_branches': args.all_branches,
                        'use_threads': not args.no_threads
                    }
                )
                html_reporter.generate_report(all_commit_results, 'commits')
            
            if args.csv_report:
                csv_reporter = CSVReportGenerator(
                    project=args.project, 
                    organization=args.organization, 
                    search_params={
                        'search_terms': args.commits,
                        'repos': [repo['name'] for repo in repos],
                        'case_sensitive': not args.case_insensitive,
                        'regex': args.regex,
                        'author': args.author,
                        'from_date': args.from_date,
                        'to_date': args.to_date,
                        'context_lines': args.lines,
                        'all_branches': args.all_branches,
                        'use_threads': not args.no_threads
                    }
                )
                csv_reporter.generate_report(all_commit_results, 'commits')

        # Similar block for search results
        if args.search and all_search_results:
            if args.html_report:
                html_reporter = HTMLReporter(
                    project=args.project, 
                    organization=args.organization, 
                    search_params={
                        'search_terms': args.search, 
                        'repos': [repo['name'] for repo in repos],
                        'case_sensitive': not args.case_insensitive,
                        'regex': args.regex,
                        'extensions': list(extensions) if extensions else ['All'],
                        'context_lines': args.lines,
                        'all_branches': args.all_branches,
                        'use_threads': not args.no_threads
                    }
                )
                html_reporter.generate_report(all_search_results, 'search')
            
            if args.csv_report:
                csv_reporter = CSVReportGenerator(
                    project=args.project, 
                    organization=args.organization, 
                    search_params={
                        'search_terms': args.search,
                        'repos': [repo['name'] for repo in repos],
                        'case_sensitive': not args.case_insensitive,
                        'regex': args.regex,
                        'extensions': list(extensions) if extensions else ['All'],
                        'context_lines': args.lines,
                        'all_branches': args.all_branches,
                        'use_threads': not args.no_threads
                    }
                )
                csv_reporter.generate_report(all_search_results, 'search')

        # Step 4.4: Display repository tree if no search is specified
        elif not args.search and args.list_contents:
            if args.all_branches:
                for branch in sorted(branch_list):
                    log.info(f"Repository: {repo['name']}")
                    log.info(f"Branch: {branch}")
                    log.info("Contents:")
                    try:
                        client.print_repository_tree(args.project, repo['id'], branch)
                    except requests.exceptions.RequestException as e:
                        log.error(f"Error accessing repository contents for branch {branch}: {str(e)}")
            else:
                log.info(f"Repository: {repo['name']}")
                log.info("Contents:")
                try:
                    client.print_repository_tree(args.project, repo['id'])
                except requests.exceptions.RequestException as e:
                    log.error(f"Error accessing repository contents: {str(e)}")

        # Step 4.5: List commits if --list-commits is specified
        elif not args.search and args.list_commits:
            log.info(f"Repository: {repo['name']}")
            try:
                # If all-branches is specified, iterate through all branches
                if args.all_branches:
                    branches_to_check = branch_list
                else:
                    # Otherwise, use default branch or None
                    branches_to_check = [format_branch_name(default_branch) if default_branch != 'N/A' else None]
                
                # Track unique commits across branches
                unique_commits = {}
                
                for branch in branches_to_check:
                    log.info(f"Checking branch: {branch or 'Default'}")
                    commits = client.get_commits(
                        args.project, 
                        repo['id'], 
                        branch=branch,
                        author=args.author,
                        from_date=args.from_date,
                        to_date=args.to_date
                    )

                    # Collect unique commits
                    for commit in commits:
                        # Use a unique key that includes branch
                        commit_key = commit['commitId']
                        if commit_key not in unique_commits:
                            # Add branch information to the commit
                            commit_with_branch = commit.copy()
                            commit_with_branch['branch'] = branch or 'Default'
                            unique_commits[commit_key] = commit_with_branch

                # Convert unique commits to list and sort by date
                commits_list = list(unique_commits.values())
                commits_list.sort(key=lambda x: x['author']['date'], reverse=True)

                if commits_list:
                    log.success(f"Found {len(commits_list)} unique commits:")
                    for commit in commits_list:
                        # Format commit date
                        commit_date = datetime.strptime(
                            commit['author']['date'], 
                            '%Y-%m-%dT%H:%M:%SZ'
                        ).replace(tzinfo=timezone.utc)

                        print("\n" + "-" * 80)
                        print(f"Branch: {commit.get('branch', 'Unknown')}")
                        print(f"Commit ID: {commit['commitId']}")
                        print(f"Author: {commit['author']['name']} <{commit['author']['email']}>")
                        print(f"Date: {commit_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"Message: {commit.get('comment', 'No commit message')}")
                        
                        # Display change counts
                        change_counts = commit.get('changeCounts', {})
                        if change_counts:
                            print("Changes:")
                            for change_type, count in change_counts.items():
                                print(f"  {change_type}: {count}")
                else:
                    log.warn("No commits found")

            except requests.exceptions.RequestException as e:
                log.error(f"Error listing commits: {str(e)}")

        print()
            
    except (ValueError, requests.exceptions.RequestException) as e:
        log.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    mimetypes.init()
    
    try:
        main()
    except KeyboardInterrupt:
        log.error("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
