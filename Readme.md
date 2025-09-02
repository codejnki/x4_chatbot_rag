```
python -m venv .venv                          
.\.venv\Scripts\activate
```

---
AI Assistant Project Brief

Last Updated: Tue Sep 02 2025

This document serves as a "state-of-the-project" brief for an AI programming assistant. Its purpose is to provide all the necessary context to resume development without needing to re-read the entire codebase.
Project Goal

To build a 100% local, Retrieval-Augmented Generation (RAG) chatbot that is an expert on the video game "X4 Foundations" and can act as an in-character improv partner named "Larry."
Core Architecture: The "Researcher/Actor" Model

After initial development, we identified critical flaws in standard RAG: retrieved documents can be irrelevant or factually conflicting, and handling multiple keywords in a query is difficult. To solve this, we designed and implemented a sophisticated two-stage LLM pipeline:

    The "Researcher" (Fact-Finding Stage):
        Receives multiple documents retrieved via a hybrid keyword/semantic search.
        Is given a synthetic, factual task: "Summarize the key information about [keywords] from the provided text."
        Its sole job is to analyze the documents and synthesize a single, dense paragraph of verified, relevant facts.
        If no relevant facts can be found, it returns a NO_CLEAR_ANSWER signal.

    The "Actor" (Performance Stage):
        This is the final, user-facing LLM call (the "Larry" persona).
        It receives the user's original, conversational query.
        Crucially, it receives the clean, synthesized paragraph from the Researcher as its "context."
        This allows the Actor to focus entirely on creative, in-character performance, using the pre-vetted context as its ground truth.

Project Status & Recent Breakthroughs

The core "Researcher/Actor" pipeline is now fully implemented, debugged, and validated. We have successfully solved the key design challenges:

    Resolved Type Mismatch Bug: The Researcher outputs a string, but the LangChain actor_chain expected a List[Document]. We fixed this by wrapping the researcher's output string in a Document object before passing it to the actor (final_documents = [Document(page_content=final_context_str)]).

    Refined Researcher Logic: The Researcher initially failed on subjective queries (e.g., "What do you feel like smuggling?"). It was trying to answer the user's conversational question directly from factual text. We fixed this by changing its task. It no longer tries to answer the user's question; instead, it factually summarizes the retrieved information about the query's keywords. This decouples fact-finding from performance and was the key to making the architecture work.

    Successful Validation: We confirmed the new architecture works with the "spaceweed or spacefuel" test. The Researcher correctly extracted factual data about the two wares, and the Actor used that data to deliver a creative, persona-driven response that was grounded in facts.

Next Steps: Project Hardening & Stability Testing

The current phase is no longer about bug-fixing the core pipeline, but about making the project robust and reliable. The immediate goals are:

    Code Cleanup: Refactor the codebase for clarity, add docstrings and comments, and improve type hinting.
    Project Tooling: Create a Makefile for easy setup and execution (make install, make run).
    Documentation: Complete this README.md file.
    Long-Conversation "Soak Test": Conduct an extended conversation with the chatbot to test its ability to maintain context and persona over many turns, specifically testing the chat_history mechanism.
