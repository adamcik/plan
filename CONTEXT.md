# Plan

Plan is a server-rendered timetable generator for educational institutions.

## Language

**Course**:
An educational offering available in a particular semester. A course has a code, name, examinations, and lectures.
_Avoid_: Class, module, subject

**Course selection**:
A timetable's inclusion of a course, with an optional display-name override and chosen groups.
_Avoid_: Enrollment, registration, subscription

**Examination**:
An assessed event for a course, with its type and any known handout, start, and duration details.
_Avoid_: Test

**Group**:
A university programme or other cohort to which lectures may belong. Lectures without a defined group belong to the fallback group `Other`.
_Avoid_: Class, section

**Lecture**:
A scheduled teaching event within a course. A lecture may belong to one or more groups and can provide a stream link.
_Avoid_: Class, session

**Location**:
A campus or other teaching site at which a course is offered. A course may be offered at more than one location.
_Avoid_: Campus when referring specifically to the university's campus structure

**Semester**:
One spring or fall academic period in a particular year.
_Avoid_: Term

**Timetable**:
A semester-specific, openly shared collection of course selections and their lecture preferences, identified by its timetable slug.
_Avoid_: Schedule, calendar

**Timetable slug**:
A public, human-chosen identifier for a timetable that is unique within its semester. Anyone who knows it can view and change that timetable.
_Avoid_: Username, account name, user ID, claim
