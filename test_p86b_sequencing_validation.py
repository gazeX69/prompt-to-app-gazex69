import sys
import logging
from pathlib import Path
from backend.core.sequencing.validator import SequencingValidator
from backend.planner.minimal_mutation import MutationEdit, EditStrategy

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def create_react_todo_mutations():
    return [
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/types/todo.ts",
            location="new_file",
            code_to_insert="export interface Todo { id: string; text: string; completed: boolean; }"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/providers/TodoProvider.tsx",
            location="new_file",
            code_to_insert="import { Todo } from '../types/todo';\nexport const TodoContext = React.createContext<Todo[]>([]);"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/components/TodoList.tsx",
            location="new_file",
            code_to_insert="import { TodoContext } from '../providers/TodoProvider';\nexport function TodoList() { const todos = useContext(TodoContext); return <div></div>; }"
        ),
        MutationEdit(
            strategy=EditStrategy.MODIFY_MINIMAL,
            target_file="src/App.tsx",
            location="inject",
            code_to_insert="import { TodoProvider } from './providers/TodoProvider';\nimport { TodoList } from './components/TodoList';\n<TodoProvider><TodoList /></TodoProvider>"
        )
    ]

def create_react_dashboard_mutations():
    return [
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/components/Chart.tsx",
            location="new_file",
            code_to_insert="export function Chart() { return <canvas></canvas>; }"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/components/Sidebar.tsx",
            location="new_file",
            code_to_insert="import { useLocation } from 'react-router-dom';\nexport function Sidebar() { const loc = useLocation(); return <aside></aside>; }"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="src/routes/DashboardRoute.tsx",
            location="new_file",
            code_to_insert="import { Chart } from '../components/Chart';\nimport { Sidebar } from '../components/Sidebar';\n<Route path='/dashboard' element={<><Sidebar /><Chart /></>} />"
        ),
        MutationEdit(
            strategy=EditStrategy.MODIFY_MINIMAL,
            target_file="src/App.tsx",
            location="inject",
            code_to_insert="import { BrowserRouter } from 'react-router-dom';\n<BrowserRouter>/* router_setup */</BrowserRouter>"
        )
    ]

def create_php_login_mutations():
    # Adding some cyclic/bad ordering for conflict detection tests
    return [
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="includes/auth.php",
            location="new_file",
            code_to_insert="require_once 'db.php';\nfunction login() { /*...*/ }"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="includes/db.php",
            location="new_file",
            code_to_insert="require_once 'auth.php';\nfunction connect() { /*...*/ }"
        ),
        MutationEdit(
            strategy=EditStrategy.CREATE_NEW_FILE,
            target_file="login.php",
            location="new_file",
            code_to_insert="require_once 'includes/auth.php';\nlogin();"
        )
    ]

def main():
    root = Path(__file__).parent
    validator = SequencingValidator(root)
    
    print("==================================================")
    print("P8.6B — SEQUENCING COGNITION VALIDATION RUN")
    print("==================================================")
    
    # 1. React Todo App
    print("\nRunning Validation: React Todo App")
    todo_muts = create_react_todo_mutations()
    todo_report = validator.validate_sequence("react_todo", todo_muts)
    print(f"- Stability Score: {todo_report['quality_audit']['stability_score']}")
    print(f"- Max Depth: {todo_report['minimality_analysis']['max_sequence_depth']}")
    print(f"- Missing Prereqs: {todo_report['prerequisite_validation']['missing_prerequisites']}")
    
    # 2. React Dashboard App
    print("\nRunning Validation: React Dashboard App")
    dash_muts = create_react_dashboard_mutations()
    dash_report = validator.validate_sequence("react_dashboard", dash_muts)
    print(f"- Stability Score: {dash_report['quality_audit']['stability_score']}")
    print(f"- Max Depth: {dash_report['minimality_analysis']['max_sequence_depth']}")
    print(f"- Missing Prereqs: {dash_report['prerequisite_validation']['missing_prerequisites']}")
    
    # 3. PHP Login App (Conflict Analysis)
    print("\nRunning Validation: PHP Login App")
    php_muts = create_php_login_mutations()
    php_report = validator.validate_sequence("php_login", php_muts)
    print(f"- Stability Score: {php_report['quality_audit']['stability_score']}")
    print(f"- Max Depth: {php_report['minimality_analysis']['max_sequence_depth']}")
    print(f"- Circular Dependencies: {php_report['conflict_analysis']['circular_dependencies']}")
    
    print("\n==================================================")
    print("ALL VALIDATION REPORTS PERSISTED TO .orchestration/p8/sequencing_validation/")
    print("VALIDATION SUCCESSFUL: DRY-RUN ONLY.")
    print("==================================================")

if __name__ == '__main__':
    main()
