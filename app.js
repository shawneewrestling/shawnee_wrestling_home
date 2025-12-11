// Shawnee Wrestling Data Loader

class WrestlingDataLoader {
    constructor() {
        // Add cache buster to force fresh data
        this.dataUrl = 'data/wrestling_data.json?v=' + new Date().getTime();
        this.data = null;
    }

    async loadData() {
        try {
            const response = await fetch(this.dataUrl, {
                cache: 'no-store'  // Force no caching
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            this.data = await response.json();
            this.renderAll();
        } catch (error) {
            console.error('Error loading wrestling data:', error);
            this.showError();
        }
    }

    renderAll() {
        this.renderLastUpdated();
        this.renderRoster();
        this.renderSchedule();
        this.renderResults();
    }

    renderLastUpdated() {
        const lastUpdatedEl = document.getElementById('lastUpdated');
        if (this.data && this.data.metadata && this.data.metadata.last_updated) {
            const date = new Date(this.data.metadata.last_updated);
            lastUpdatedEl.textContent = date.toLocaleString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
                timeZone: 'America/New_York'  // EST timezone
            });
        } else {
            lastUpdatedEl.textContent = 'Unknown';
        }
    }

    renderRoster() {
        const tbody = document.querySelector('#rosterTable tbody');
        
        if (!this.data || !this.data.roster || this.data.roster.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="no-data">No roster data available</td></tr>';
            return;
        }

        // Sort by weight class (numerically)
        const sortedRoster = [...this.data.roster].sort((a, b) => {
            const weightA = parseInt(a.weight_class) || 999;
            const weightB = parseInt(b.weight_class) || 999;
            return weightA - weightB;
        });

        tbody.innerHTML = sortedRoster.map(wrestler => `
            <tr>
                <td><strong>${this.escapeHtml(wrestler.name)}</strong></td>
                <td>${this.escapeHtml(wrestler.weight_class)}</td>
                <td>${this.escapeHtml(wrestler.grade)}</td>
                <td>${this.escapeHtml(wrestler.record || 'N/A')}</td>
            </tr>
        `).join('');
    }

    renderSchedule() {
        const tbody = document.querySelector('#scheduleTable tbody');
        
        if (!this.data || !this.data.schedule || this.data.schedule.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">No schedule data available</td></tr>';
            return;
        }

        tbody.innerHTML = this.data.schedule.map(match => {
            const resultClass = this.getResultClass(match.result);
            return `
                <tr>
                    <td>${this.escapeHtml(match.date)}</td>
                    <td><strong>${this.escapeHtml(match.opponent)}</strong></td>
                    <td>${this.escapeHtml(match.location)}</td>
                    <td>${this.escapeHtml(match.time)}</td>
                    <td class="${resultClass}">${this.escapeHtml(match.result || 'TBD')}</td>
                </tr>
            `;
        }).join('');
    }

    renderResults() {
        const tbody = document.querySelector('#resultsTable tbody');
        
        if (!this.data || !this.results || this.data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">No results available yet. Check back after matches begin!</td></tr>';
            return;
        }

        tbody.innerHTML = this.data.results.map(result => {
            const resultClass = this.getResultClass(result.result);
            return `
                <tr>
                    <td>${this.escapeHtml(result.date)}</td>
                    <td><strong>${this.escapeHtml(result.opponent)}</strong></td>
                    <td>${this.escapeHtml(result.score)}</td>
                    <td class="${resultClass}">${this.escapeHtml(result.result)}</td>
                    <td>${this.escapeHtml(result.location)}</td>
                </tr>
            `;
        }).join('');
    }

    getResultClass(result) {
        if (!result || result === 'TBD') return 'result-tbd';
        
        const resultLower = result.toLowerCase();
        if (resultLower.includes('win') || resultLower.includes('w')) {
            return 'result-win';
        } else if (resultLower.includes('loss') || resultLower.includes('l')) {
            return 'result-loss';
        }
        return 'result-tbd';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError() {
        const sections = ['rosterTable', 'scheduleTable', 'resultsTable'];
        sections.forEach(id => {
            const tbody = document.querySelector(`#${id} tbody`);
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">Error loading data. Please try again later.</td></tr>';
        });
        
        document.getElementById('lastUpdated').textContent = 'Error loading data';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const loader = new WrestlingDataLoader();
    loader.loadData();
});

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
