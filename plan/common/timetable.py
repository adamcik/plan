from plan.common.models import Lecture

class Timetable:
    def __init__(self, lectures, rooms={}):
        self.lecture_queryset = lectures
        self.lectures = []
        self.table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]
        self.span = [1] * 5

        self.rooms = rooms

    def place_lectures(self):
        '''Add basics to datastructure'''

        for i, lecture in enumerate(self.lecture_queryset):
            if lecture.exclude:
                continue

            start = lecture.start_time - Lecture.START[0][0]
            end = lecture.end_time - Lecture.END[0][0]
            rowspan = end - start + 1

            first = start

            # Try to find leftmost row that can fit our lecture, if we run out of
            # rows to test, ie IndexError, we append a fresh one to work with
            try:
                row = 0
                while start <= end:
                    if self.table[start][lecture.day][row]:
                        # One of our time slots is taken, bump the row number and
                        # restart our search
                        row += 1
                        start = first
                    else:
                        start += 1

            except IndexError:
                # We ran out of rows to check, simply append a new row
                for j in range(len(Lecture.START)):
                    self.table[j][lecture.day].append({})

                # Update the header colspan
                self.span[lecture.day] += 1

            start = first
            remove = False

            while start <= end:
                # Replace the cell we found with a base containing info about our
                # lecture
                self.table[start][lecture.day][row] = {
                    'lecture': lecture,
                    'rowspan': rowspan,
                    'remove': remove,
                }

                # Add lecture to our supplementary data structure and set the
                # remove flag.
                if not remove:
                    remove = True
                    self.lectures.append({
                        'height': rowspan,
                        'i': start,
                        'j': lecture.day,
                        'k': row,
                    })

                start += 1

    def do_expansion(self):
        for lecture in self.lectures:
            # Loop over supplementary data structure using this to figure out which
            # colspan expansions are safe
            i = lecture['i']
            j = lecture['j']
            k = lecture['k']

            height = lecture['height']

            expand_by = 1

            # Add rooms
            r = self.rooms.get(self.table[i][j][k]['lecture'].id, [])

            self.table[i][j][k]['lecture'].sql_rooms = r

            # Find safe expansion of colspan
            safe = True
            for l in xrange(k+1, len(self.table[i][j])):
                for m in xrange(i, i+height):
                    if self.table[m][j][l]:
                        safe = False
                        break
                if safe:
                    expand_by += 1
                else:
                    break

            self.table[i][j][k]['colspan'] = expand_by

            # Remove cells that will get replaced by colspan
            for l in xrange(k+1, k+expand_by):
                for m in xrange(i, i+height):
                    self.table[m][j][l]['remove'] = True

    def insert_times(self):
        times = zip(range(len(Lecture.START)), Lecture.START, Lecture.END)

        for i, start, end in times:
            self.table[i].insert(0, [{'time': '%s&nbsp;-&nbsp;%s' % (start[1], end[1]) }])
