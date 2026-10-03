#pragma once

#include "core/AccountSnapshot.h"

#include <QObject>
#include <QString>

// Where the tree comes from. The UI only ever talks to this port. Signals are
// emitted on the GUI thread.
class IAccountSource : public QObject
{
    Q_OBJECT

public:
    using QObject::QObject;

    // Answered by any number of progress() and then exactly one loaded() or failed().
    virtual void load() = 0;

signals:
    // stage is the headline ("Reading the folder list…"), detail an optional
    // second line ("12,000 items"). total -1 = unknown (busy indicator).
    void progress(const QString& stage, const QString& detail, qint64 done, qint64 total);

    void loaded(SnapshotPtr snapshot);
    void failed(const QString& error);
};
