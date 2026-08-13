"""Akasha's permanent internal book_tracker package.

Deliberately empty of imports. This module used to re-export `create_app`, which
meant that importing anything at all from the package built the entire FastAPI
application, including a `Settings()` that refuses to construct in production
without `USER_AGENT_CONTACT`. The backup CLI inherited that: restoring a backup
onto a bare machine failed on a validation error about an unrelated provider
setting, in exactly the situation where the operator least needs a puzzle.

Import `create_app` from `book_tracker.main`.
"""
