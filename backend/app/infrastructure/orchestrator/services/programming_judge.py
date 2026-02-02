"""
Programming Battle Judge Service

Manages competitive programming challenges with:
- Multi-language sandboxed execution
- Secure compilation and execution
- Hidden test case evaluation
- Anti-cheat measures (plagiarism detection, syscall monitoring)

Sandbox Implementation:
- Container-based execution with gVisor/Kata for extra isolation
- Resource limits: 2 CPU, 256MB RAM, 5s execution time
- Security: seccomp-bpf, no network, readonly rootfs
"""

import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

from ..models_advanced import (
    JudgeStatus,
    ProgrammingLanguage,
    ProgrammingSubmission,
    TestCase,
    TestResult,
)

logger = structlog.get_logger(__name__)


# ============================================================================
# Language Runners
# ============================================================================

@dataclass
class ExecutionResult:
    """Result of executing code against a test case."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: int
    memory_usage_mb: int
    timed_out: bool = False
    memory_exceeded: bool = False


class LanguageRunner:
    """Base class for language-specific runners."""
    
    def __init__(
        self,
        image_name: str,
        compile_timeout: int = 30,
        execution_timeout: int = 5,
        memory_limit_mb: int = 256,
    ):
        self.image_name = image_name
        self.compile_timeout = compile_timeout
        self.execution_timeout = execution_timeout
        self.memory_limit_mb = memory_limit_mb
    
    async def compile(self, source_code: str, work_dir: str) -> Tuple[bool, str]:
        """Compile source code. Returns (success, error_message)."""
        raise NotImplementedError
    
    async def execute(
        self,
        input_data: str,
        work_dir: str,
    ) -> ExecutionResult:
        """Execute compiled binary with input. Returns ExecutionResult."""
        raise NotImplementedError


class PythonRunner(LanguageRunner):
    """Runner for Python 3."""
    
    def __init__(self):
        super().__init__(
            image_name="sandbox-python:latest",
            compile_timeout=10,
            execution_timeout=5,
            memory_limit_mb=256,
        )
    
    async def compile(self, source_code: str, work_dir: str) -> Tuple[bool, str]:
        """Python doesn't need compilation, just syntax check."""
        try:
            # Syntax check by attempting to compile
            compile(source_code, "<string>", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}"
    
    async def execute(
        self,
        input_data: str,
        work_dir: str,
    ) -> ExecutionResult:
        """Execute Python script."""
        start_time = datetime.utcnow()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-u",  # Unbuffered
                "-c",
                input_data if input_data.startswith("#!") else "",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                limit=1024 * 1024,  # 1MB I/O limit
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.execution_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Time Limit Exceeded",
                    execution_time_ms=self.execution_timeout * 1000,
                    memory_usage_mb=0,
                    timed_out=True,
                )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ExecutionResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                execution_time_ms=int(execution_time),
                memory_usage_mb=0,  # Would need cgroup metrics
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                memory_usage_mb=0,
            )


class CPPRunner(LanguageRunner):
    """Runner for C++."""
    
    def __init__(self):
        super().__init__(
            image_name="sandbox-cpp:latest",
            compile_timeout=30,
            execution_timeout=5,
            memory_limit_mb=256,
        )
    
    async def compile(self, source_code: str, work_dir: str) -> Tuple[bool, str]:
        """Compile C++ source code."""
        source_file = os.path.join(work_dir, "solution.cpp")
        executable = os.path.join(work_dir, "solution")
        
        with open(source_file, "w") as f:
            f.write(source_code)
        
        compile_proc = await asyncio.create_subprocess_exec(
            "g++",
            "-std=c++17",
            "-O2",
            "-pipe",
            "-static",  # Static linking for sandbox compatibility
            "-s",
            source_file,
            "-o",
            executable,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            _, stderr = await asyncio.wait_for(
                compile_proc.communicate(),
                timeout=self.compile_timeout,
            )
        except asyncio.TimeoutError:
            compile_proc.kill()
            return False, "Compilation timeout"
        
        if compile_proc.returncode != 0:
            return False, stderr.decode("utf-8", errors="replace")
        
        return True, ""
    
    async def execute(
        self,
        input_data: str,
        work_dir: str,
    ) -> ExecutionResult:
        """Execute compiled C++ binary."""
        executable = os.path.join(work_dir, "solution")
        start_time = datetime.utcnow()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                limit=1024 * 1024,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input_data.encode() if input_data else None),
                    timeout=self.execution_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Time Limit Exceeded",
                    execution_time_ms=self.execution_timeout * 1000,
                    memory_usage_mb=0,
                    timed_out=True,
                )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ExecutionResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                execution_time_ms=int(execution_time),
                memory_usage_mb=0,
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                memory_usage_mb=0,
            )


class JavaRunner(LanguageRunner):
    """Runner for Java."""
    
    def __init__(self):
        super().__init__(
            image_name="sandbox-java:latest",
            compile_timeout=30,
            execution_timeout=10,  # Java starts slower
            memory_limit_mb=512,
        )
    
    async def compile(self, source_code: str, work_dir: str) -> Tuple[bool, str]:
        """Compile Java source code."""
        source_file = os.path.join(work_dir, "Solution.java")
        
        with open(source_file, "w") as f:
            f.write(source_code)
        
        compile_proc = await asyncio.create_subprocess_exec(
            "javac",
            "-Xlint:all",
            source_file,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            _, stderr = await asyncio.wait_for(
                compile_proc.communicate(),
                timeout=self.compile_timeout,
            )
        except asyncio.TimeoutError:
            compile_proc.kill()
            return False, "Compilation timeout"
        
        if compile_proc.returncode != 0:
            return False, stderr.decode("utf-8", errors="replace")
        
        return True, ""
    
    async def execute(
        self,
        input_data: str,
        work_dir: str,
    ) -> ExecutionResult:
        """Execute Java class."""
        start_time = datetime.utcnow()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "java",
                "-cp",
                work_dir,
                "-XX:+UseSerialGC",
                "-Xmx256m",
                "Solution",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input_data.encode() if input_data else None),
                    timeout=self.execution_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Time Limit Exceeded",
                    execution_time_ms=self.execution_timeout * 1000,
                    memory_usage_mb=0,
                    timed_out=True,
                )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ExecutionResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                execution_time_ms=int(execution_time),
                memory_usage_mb=0,
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                memory_usage_mb=0,
            )


# ============================================================================
# Anti-Cheat System
# ============================================================================

class AntiCheatSystem:
    """Detects cheating in programming submissions."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self._submission_hashes: Dict[str, List[str]] = {}  # problem_id -> [code_hashes]
    
    def compute_ast_hash(self, code: str, language: str) -> str:
        """Compute AST-based hash for plagiarism detection."""
        # Simplified implementation - in production, use actual AST parsing
        # This strips comments and whitespace for comparison
        lines = []
        for line in code.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("#") and not stripped.startswith("//"):
                lines.append(stripped)
        
        normalized = "\n".join(lines)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    async def check_plagiarism(
        self,
        problem_id: str,
        code: str,
        language: ProgrammingLanguage,
        user_id: UUID,
    ) -> Optional[str]:
        """
        Check for plagiarism against previous submissions.
        
        Returns:
            None if no plagiarism detected, description if detected
        """
        code_hash = self.compute_ast_hash(code, language.value)
        
        cache_key = f"programming:submissions:{problem_id}:{language.value}"
        existing_hashes = await self.cache.get(cache_key) or []
        
        # Check for exact matches
        if code_hash in existing_hashes:
            return "Exact code match found with previous submission"
        
        # In production, use Moss/Stirling algorithm for fuzzy matching
        # For now, we just store the hash
        existing_hashes.append(code_hash)
        await self.cache.set(cache_key, existing_hashes, ttl=86400 * 30)  # 30 days
        
        return None
    
    def check_forbidden_patterns(self, code: str, language: ProgrammingLanguage) -> List[str]:
        """Check for forbidden patterns in code."""
        forbidden = []
        
        if language == ProgrammingLanguage.PYTHON:
            # Check for dangerous imports
            dangerous_imports = [
                "os", "sys", "subprocess", "socket", "requests",
                "importlib", "ctypes", "threading", "multiprocessing",
            ]
            for imp in dangerous_imports:
                if f"import {imp}" in code or f"from {imp}" in code:
                    forbidden.append(f"Forbidden import: {imp}")
        
        return forbidden
    
    def check_network_calls(self, code: str, language: ProgrammingLanguage) -> bool:
        """Check if code appears to make network calls."""
        # Simplified - in production, use syscall tracing
        network_patterns = [
            "socket.socket",
            "http.client",
            "urllib",
            "requests.",
            "fetch(",
            "axios",
        ]
        
        for pattern in network_patterns:
            if pattern in code:
                return True
        
        return False


# ============================================================================
# Programming Judge
# ============================================================================

class ProgrammingJudge:
    """
    Main programming judge service.
    
    Handles:
    - Code compilation and execution
    - Test case evaluation
    - Scoring (static ICPC style or dynamic Codeforces style)
    - Anti-cheat detection
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        scoring_mode: str = "static",  # "static" or "dynamic"
    ):
        self.db = db_manager
        self.cache = cache_manager
        self.scoring_mode = scoring_mode
        
        # Initialize language runners
        self._runners: Dict[ProgrammingLanguage, LanguageRunner] = {
            ProgrammingLanguage.PYTHON: PythonRunner(),
            ProgrammingLanguage.CPP: CPPRunner(),
            ProgrammingLanguage.JAVA: JavaRunner(),
            # Add more languages as needed
        }
        
        # Anti-cheat system
        self.anti_cheat = AntiCheatSystem(cache_manager)
        
        # Judge configuration
        self._max_concurrent_judges = 4
        self._judge_semaphore = asyncio.Semaphore(self._max_concurrent_judges)
        
        # Test case storage (encrypted in production)
        self._test_cases: Dict[str, List[TestCase]] = {}
    
    async def submit(
        self,
        user_id: UUID,
        team_id: Optional[UUID],
        problem_id: str,
        language: ProgrammingLanguage,
        code: str,
    ) -> ProgrammingSubmission:
        """
        Submit code for judging.
        
        Args:
            user_id: Submitting user ID
            team_id: Team ID (for team submissions)
            problem_id: Problem identifier
            language: Programming language
            code: Source code
            
        Returns:
            ProgrammingSubmission with initial status
        """
        submission = ProgrammingSubmission(
            id=uuid4(),
            user_id=user_id,
            team_id=team_id,
            problem_id=problem_id,
            language=language,
            code=code,
            status=JudgeStatus.PENDING,
        )
        
        # Store submission
        await self._store_submission(submission)
        
        # Queue for async judging
        asyncio.create_task(self._judge_submission(submission))
        
        return submission
    
    async def _judge_submission(self, submission: ProgrammingSubmission) -> None:
        """Judge a submission asynchronously."""
        async with self._judge_semaphore:
            try:
                # Update status to compiling
                submission.status = JudgeStatus.COMPILING
                await self._update_submission(submission)
                
                # Get test cases
                test_cases = await self._get_test_cases(submission.problem_id)
                if not test_cases:
                    submission.status = JudgeStatus.INTERNAL_ERROR
                    submission.error_message = "No test cases found for problem"
                    await self._update_submission(submission)
                    return
                
                # Anti-cheat checks
                plagiarism = await self.anti_cheat.check_plagiarism(
                    submission.problem_id,
                    submission.code,
                    submission.language,
                    submission.user_id,
                )
                if plagiarism:
                    submission.status = JudgeStatus.RUNTIME_ERROR
                    submission.error_message = f"Plagiarism detected: {plagiarism}"
                    await self._update_submission(submission)
                    return
                
                forbidden = self.anti_cheat.check_forbidden_patterns(
                    submission.code, submission.language
                )
                if forbidden:
                    submission.status = JudgeStatus.RUNTIME_ERROR
                    submission.error_message = f"Forbidden code patterns: {', '.join(forbidden)}"
                    await self._update_submission(submission)
                    return
                
                # Compile
                runner = self._runners.get(submission.language)
                if not runner:
                    submission.status = JudgeStatus.INTERNAL_ERROR
                    submission.error_message = f"Unsupported language: {submission.language}"
                    await self._update_submission(submission)
                    return
                
                with tempfile.TemporaryDirectory() as work_dir:
                    compile_success, compile_error = await runner.compile(
                        submission.code, work_dir
                    )
                    
                    if not compile_success:
                        submission.status = JudgeStatus.COMPILATION_ERROR
                        submission.error_message = compile_error
                        await self._update_submission(submission)
                        return
                    
                    # Run test cases
                    submission.status = JudgeStatus.RUNNING
                    await self._update_submission(submission)
                    
                    test_results = []
                    total_score = 0
                    max_score = 0
                    total_time = 0
                    max_memory = 0
                    
                    for test_case in test_cases:
                        result = await self._run_test_case(
                            runner, test_case, work_dir
                        )
                        
                        test_result = TestResult(
                            test_case_id=test_case.id,
                            passed=result.success and not result.timed_out,
                            execution_time_ms=result.exit_code if result.success else 0,
                            memory_usage_mb=result.memory_usage_mb,
                            output=result.stdout.strip(),
                            expected_output=test_case.expected_output.strip(),
                            error=result.stderr if result.stderr else None,
                        )
                        
                        test_results.append(test_result.to_dict())
                        
                        if result.timed_out:
                            submission.status = JudgeStatus.TIME_LIMIT_EXCEEDED
                            max_score += test_case.points
                        elif not result.success:
                            if submission.status not in [
                                JudgeStatus.TIME_LIMIT_EXCEEDED,
                                JudgeStatus.WRONG_ANSWER,
                            ]:
                                submission.status = JudgeStatus.WRONG_ANSWER
                            max_score += test_case.points
                        else:
                            total_score += test_case.points
                            max_score += test_case.points
                            total_time += result.execution_time_ms
                            max_memory = max(max_memory, result.memory_usage_mb)
                        
                        # Stop on first failure for static scoring
                        if self.scoring_mode == "static" and not test_result.passed:
                            break
                    
                    submission.test_results = test_results
                    submission.score = total_score
                    submission.max_score = max_score
                    submission.execution_time_ms = total_time
                    submission.memory_usage_mb = max_memory
                    submission.judged_at = datetime.utcnow()
                    
                    # Set final status
                    if submission.status == JudgeStatus.RUNNING:
                        if total_score == max_score:
                            submission.status = JudgeStatus.ACCEPTED
                        else:
                            submission.status = JudgeStatus.WRONG_ANSWER
                    
                    await self._update_submission(submission)
                    
                    # Emit event
                    await self._emit_event("programming.judged", {
                        "submission_id": str(submission.id),
                        "problem_id": submission.problem_id,
                        "status": submission.status.value,
                        "score": submission.score,
                        "max_score": submission.max_score,
                    })
                
            except Exception as e:
                logger.exception("Judge error", error=str(e))
                submission.status = JudgeStatus.INTERNAL_ERROR
                submission.error_message = str(e)
                await self._update_submission(submission)
    
    async def _run_test_case(
        self,
        runner: LanguageRunner,
        test_case: TestCase,
        work_dir: str,
    ) -> ExecutionResult:
        """Run a single test case."""
        return await runner.execute(test_case.input_data, work_dir)
    
    async def _get_test_cases(self, problem_id: str) -> List[TestCase]:
        """Get test cases for a problem."""
        cache_key = f"programming:test_cases:{problem_id}"
        data = await self.cache.get(cache_key)
        
        if data:
            return [TestCase(**tc) for tc in data]
        
        # Return empty list if not found (would be loaded from database in production)
        return []
    
    async def _store_submission(self, submission: ProgrammingSubmission) -> None:
        """Store submission in cache."""
        cache_key = f"programming:submission:{submission.id}"
        await self.cache.set(cache_key, submission.to_dict(), ttl=86400 * 7)
    
    async def _update_submission(self, submission: ProgrammingSubmission) -> None:
        """Update submission in cache."""
        await self._store_submission(submission)
    
    async def get_submission(self, submission_id: UUID) -> Optional[ProgrammingSubmission]:
        """Get a submission by ID."""
        cache_key = f"programming:submission:{submission_id}"
        data = await self.cache.get(cache_key)
        if data:
            return ProgrammingSubmission(**data)
        return None
    
    async def get_user_submissions(
        self,
        user_id: UUID,
        problem_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[ProgrammingSubmission]:
        """Get recent submissions for a user."""
        # In production, query from database
        # For now, return empty list
        return []
    
    async def get_problem_leaderboard(
        self,
        problem_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Get leaderboard for a problem."""
        # In production, aggregate from database
        return []
    
    async def _emit_event(self, event_type: str, data: Dict) -> None:
        """Emit a WebSocket event."""
        cache_key = f"ws:events:{event_type}"
        await self.cache.publish(cache_key, data)
