# Supernaut Take Home Task

## Purpose

Our company offers a digital product on a subscription basis. Users sign up and pay via Stripe.
We need a backend service that can determine whether a user currently has access to the
product—i.e., whether their subscription is active or canceled.

Stripe communicates subscription events to us via webhooks. These webhook events are the
only source of truth for subscription status. Your task is to design and implement a minimal
backend system that listens to these events and maintains an accurate representation of
subscription status over time.

This is a design-focused assignment. You are expected to define the minimum needed set
of application-level data structures and webhook events required to track subscription status
and ensure consistency in response to relevant Stripe events. You do not need to integrate with
Stripe directly. Mock webhook payloads should be used to simulate event delivery (i.e. using
Postman).

We want to see how you think and reason about basic product integrations. Good luck!

## Deliverables

Provide a link to a code repository (e.g. GitHub, GitLab) that includes the following:

1. An API application (in a language and framework of your choice) with:

    - A webhook endpoint that accepts POST requests containing mock Stripe
      webhook payloads.
    - Logic that updates the application's data based on those webhook events.

2. A minimal set of data models or structures that represent subscription status within
   the system. Persistence can be implemented with a lightweight database or simply
   initialized in memory - your choice.
3. A README file that includes:

    - Instructions to run the project.
    - Description of data structures.
    - Explanation of why these webhook events were chosen and how they’re handled
    - A section describing any assumptions, limitations, or other relevant design
      considerations, given the open-ended nature of the task.

4. Example mock webhook payloads that simulate relevant subscription events.
5. No frontend, no live/test connection to Stripe is needed.