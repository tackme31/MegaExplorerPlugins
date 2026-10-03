#include "core/SizeNode.h"

#include <QTest>

class TestSizeNode : public QObject
{
    Q_OBJECT

private slots:
    void finalizeAggregatesAndSorts()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        SizeNode* drive = root.addFolder(QStringLiteral("Cloud Drive"));
        SizeNode* small = drive->addFolder(QStringLiteral("small"));
        small->addFile(QStringLiteral("a.txt"), 10, 100);
        SizeNode* big = drive->addFolder(QStringLiteral("big"));
        big->addFile(QStringLiteral("b.bin"), 500, 50);
        big->addFile(QStringLiteral("c.bin"), 300, 300);
        drive->addFile(QStringLiteral("loose.dat"), 100, 10);
        drive->addFolder(QStringLiteral("empty"));

        finalizeTree(root);

        QCOMPARE(root.size, 910);
        QCOMPARE(root.fileCount, 4);
        QCOMPARE(drive->size, 910);
        QCOMPARE(big->size, 800);
        QCOMPARE(big->mtime, 300);
        QCOMPARE(drive->mtime, 300);

        QCOMPARE(drive->children.size(), std::size_t(4));
        QCOMPARE(drive->children[0]->name, QStringLiteral("big"));
        QCOMPARE(drive->children[1]->name, QStringLiteral("loose.dat"));
        QCOMPARE(drive->children[2]->name, QStringLiteral("small"));
        QCOMPARE(drive->children[3]->name, QStringLiteral("empty"));
        for (std::size_t i = 0; i < drive->children.size(); ++i)
        {
            QCOMPARE(drive->children[i]->row, static_cast<int>(i));
        }
        QCOMPARE(big->children[0]->name, QStringLiteral("b.bin"));
    }

    void tiesSortByName()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        root.addFile(QStringLiteral("b"), 5);
        root.addFile(QStringLiteral("A"), 5);
        finalizeTree(root);
        QCOMPARE(root.children[0]->name, QStringLiteral("A"));
    }

    void pathSkipsInvisibleRoot()
    {
        SizeNode root;
        root.kind = NodeKind::Folder;
        SizeNode* file = root.addFolder(QStringLiteral("Cloud Drive"))
                             ->addFolder(QStringLiteral("Photos"))
                             ->addFile(QStringLiteral("a.jpg"), 1);
        QCOMPARE(file->path(), QStringLiteral("Cloud Drive/Photos/a.jpg"));
        QCOMPARE(root.path(), QString());
    }

    void findSamePathAcrossTrees()
    {
        SizeNode oldRoot;
        oldRoot.kind = NodeKind::Folder;
        SizeNode* oldPhotos =
            oldRoot.addFolder(QStringLiteral("Cloud Drive"))->addFolder(QStringLiteral("Photos"));
        SizeNode* oldTrip = oldPhotos->addFolder(QStringLiteral("Trip"));

        SizeNode newRoot;
        newRoot.kind = NodeKind::Folder;
        SizeNode* drive = newRoot.addFolder(QStringLiteral("Cloud Drive"));
        drive->addFile(QStringLiteral("Photos"), 5); // a file with the name does not count
        SizeNode* photos = drive->addFolder(QStringLiteral("Photos"));

        QCOMPARE(findSamePath(newRoot, *oldPhotos), photos);
        // Trip is gone: fall back to the deepest ancestor that still exists.
        QCOMPARE(findSamePath(newRoot, *oldTrip), photos);
        QCOMPARE(findSamePath(newRoot, oldRoot), &newRoot);

        SizeNode emptyRoot;
        emptyRoot.kind = NodeKind::Folder;
        QCOMPARE(findSamePath(emptyRoot, *oldTrip), &emptyRoot);
    }

    void extension_data()
    {
        QTest::addColumn<QString>("name");
        QTest::addColumn<QString>("expected");
        QTest::newRow("simple") << "photo.JPG" << "jpg";
        QTest::newRow("double") << "archive.tar.gz" << "gz";
        QTest::newRow("none") << "README" << "";
        QTest::newRow("dotfile") << ".gitignore" << "";
        QTest::newRow("trailing dot") << "odd." << "";
    }

    void extension()
    {
        QFETCH(QString, name);
        QFETCH(QString, expected);
        SizeNode root;
        root.kind = NodeKind::Folder;
        QCOMPARE(root.addFile(name, 1)->extension(), expected);
        QCOMPARE(root.addFolder(name)->extension(), QString());
    }
};

QTEST_GUILESS_MAIN(TestSizeNode)
#include "tst_sizenode.moc"
