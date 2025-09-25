# Finance Dashboard - Planning Document

## Project Goal
Build a personal finance dashboard for Dara and Tom to track income, spending, and budgeting with category-based analysis and manual transaction categorization.

## Target User Experience (Based on Chase Screenshots)

### Core Features
1. **Monthly View** - Primary interface showing one month at a time
2. **Income vs Spending** - Bar chart showing monthly totals with income/spending breakdown
3. **Category Breakdown** - Pie chart showing spending by category with percentages
4. **Transaction Details** - Expandable categories showing individual transactions
5. **Manual Categorization** - Ability to edit/reassign transaction categories
6. **Multi-Month Navigation** - Switch between months easily

### Key UI Elements from Screenshots
- Time period selector (Monthly/Quarterly/Yearly)
- Account filter dropdown ("All accounts")
- Month/year navigation (Sep 2025)
- Spending total prominently displayed ($2,046.51)
- Category table with: Category, Amount spent, Percent of total
- Pie chart visualization with category colors
- Transaction list with: Date, Description, Account, Category, Amount
- Category reassignment dropdowns per transaction

## Technical Challenges to Solve

### 1. Data Ingestion
- **Input**: Multiple CSV formats from different banks/sources
- **Challenge**: Each bank has different column names, date formats, transaction descriptions
- **Solution Needed**: Flexible CSV parser with mapping/transformation rules

### 2. Transaction Categorization
- **Initial**: Auto-categorization based on merchant names/patterns
- **Override**: Manual category reassignment with persistence
- **Categories**: Need predefined category list (Food & drink, Groceries, Bills & utilities, etc.)

### 3. Data Storage
- **Challenge**: Need to persist uploaded data, categorizations, and user preferences
- **Options**: SQLite database vs JSON files vs cloud storage
- **Requirements**: Fast queries for monthly aggregations, category breakdowns

### 4. State Management
- **Challenge**: Track which transactions have been manually categorized
- **Requirements**: Remember user categorization choices, handle re-uploads

## Proposed Architecture

### Phase 1: Core Data Pipeline
```
Raw CSV Upload → Data Parsing → Transaction Normalization → Category Assignment → Storage
```

### Phase 2: Basic Dashboard
```
Stored Data → Monthly Aggregation → Charts (Bar + Pie) → Transaction List
```

### Phase 3: Interactive Features
```
Category Editor → Transaction Recategorization → Budget Setting → Multi-Month Views
```

## Data Model (Preliminary)

### Transaction Schema
```python
{
    "id": "unique_hash",
    "date": "2025-09-22",
    "description": "STARBUCKS STORE 07925",
    "amount": -7.45,  # negative for spending, positive for income
    "account": "Chase Freedom (...2568)",
    "category": "Food & drink",
    "category_source": "auto|manual",  # track if user manually set
    "raw_description": "original text from CSV"
}
```

### Categories
- Food & drink
- Groceries
- Bills & utilities
- Shopping
- Gas
- Travel
- Health & wellness
- Entertainment
- Fees & adjustments
- Income
- [Custom categories]

## Key Questions to Resolve

1. **Data Input Format**: What do the actual CSV files look like? Column names, date formats, etc.
2. **Multi-User**: Is this just for Dara & Tom, or do we need user accounts?
3. **Data Persistence**: Local files vs database vs cloud storage?
4. **Budget Features**: Do we need budget setting/tracking beyond spending visualization?
5. **Account Handling**: How many accounts will they have? Different banks?

## Success Metrics

### MVP Success (Phase 1)
- [ ] Upload any CSV transaction file
- [ ] View monthly spending total
- [ ] See spending breakdown by category (pie chart)
- [ ] View individual transactions in categories

### Full Success (Phase 3)
- [ ] Manual category reassignment
- [ ] Multi-month comparison
- [ ] Budget tracking
- [ ] Export capabilities
- [ ] Account filtering

## Next Steps

1. **Data Discovery**: Get sample CSV files to understand input formats
2. **MVP Scope**: Define minimal viable product boundaries
3. **Architecture Decision**: Choose storage/persistence approach
4. **UI Mockups**: Design Streamlit layout matching Chase UX
5. **Implementation Plan**: Break into concrete development tasks

---

*This document should guide our development approach and help us make smart tradeoffs between features and complexity.*