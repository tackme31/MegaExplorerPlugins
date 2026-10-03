#include "core/TreeBuilder.h"

#include <QJsonObject>
#include <QTest>

namespace
{

QJsonObject folder(const char* handle, const char* parent, const char* name)
{
    return {{"handle", handle}, {"parent", parent}, {"name", name}, {"type", "folder"}};
}

QJsonObject file(const char* handle, const char* parent, const char* name, qint64 size, qint64 mtime)
{
    return {{"handle", handle},
            {"parent", parent},
            {"name", name},
            {"type", "file"},
            {"size", size},
            {"mtime", mtime}};
}

} // namespace

class TestTreeBuilder : public QObject
{
    Q_OBJECT

private slots:
    void buildsTreeFromPreOrderItems()
    {
        TreeBuilder builder;
        builder.addRoot(QStringLiteral("R1"), QStringLiteral("Photos"));
        QVERIFY(builder.addItem(folder("F1", "R1", "2024")));
        QVERIFY(builder.addItem(file("A1", "F1", "a.jpg", 300, 20)));
        QVERIFY(builder.addItem(file("A2", "R1", "b.jpg", 100, 10)));
        QCOMPARE(builder.itemCount(), 3);

        const SnapshotPtr snapshot = builder.take();
        const SizeNode& root = *snapshot->root;
        QCOMPARE(root.children.size(), 1u);
        const SizeNode& photos = *root.children[0];
        QCOMPARE(photos.name, QStringLiteral("Photos"));
        QCOMPARE(photos.handle, QStringLiteral("R1"));
        QCOMPARE(photos.size, 400);
        QCOMPARE(photos.fileCount, 2);
        // Largest first.
        QCOMPARE(photos.children[0]->handle, QStringLiteral("F1"));
        QCOMPARE(photos.children[0]->children[0]->handle, QStringLiteral("A1"));
        QCOMPARE(photos.children[0]->children[0]->mtime, 20);
        QCOMPARE(photos.children[1]->name, QStringLiteral("b.jpg"));
    }

    void severalRootsAreTopLevelSiblings()
    {
        TreeBuilder builder;
        builder.addRoot(QStringLiteral("R1"), QStringLiteral("small"));
        builder.addRoot(QStringLiteral("R2"), QStringLiteral("big"));
        builder.addItem(file("A1", "R1", "a", 1, 0));
        builder.addItem(file("B1", "R2", "b", 9, 0));

        const SnapshotPtr snapshot = builder.take();
        QCOMPARE(snapshot->root->children.size(), 2u);
        QCOMPARE(snapshot->root->children[0]->name, QStringLiteral("big"));
        QCOMPARE(snapshot->root->size, 10);
    }

    void unrevealableRootHasNoHandleButStillTakesChildren()
    {
        TreeBuilder builder;
        builder.addRoot(QStringLiteral("R1"), QStringLiteral("Cloud Drive"), false);
        QVERIFY(builder.addItem(file("A1", "R1", "a", 5, 0)));

        const SnapshotPtr snapshot = builder.take();
        QVERIFY(snapshot->root->children[0]->handle.isEmpty());
        QCOMPARE(snapshot->root->children[0]->children[0]->handle, QStringLiteral("A1"));
    }

    void itemWithUnknownParentIsDropped()
    {
        TreeBuilder builder;
        builder.addRoot(QStringLiteral("R1"), QStringLiteral("root"));
        QVERIFY(!builder.addItem(file("A1", "nowhere", "a", 5, 0)));
        QCOMPARE(builder.itemCount(), 0);
        QCOMPARE(builder.take()->root->size, 0);
    }

    void takeLeavesBuilderEmpty()
    {
        TreeBuilder builder;
        builder.addRoot(QStringLiteral("R1"), QStringLiteral("root"));
        builder.addItem(file("A1", "R1", "a", 5, 0));
        builder.take();
        QCOMPARE(builder.itemCount(), 0);
        QVERIFY(!builder.addItem(file("A2", "R1", "b", 5, 0)));
        QCOMPARE(builder.take()->root->children.size(), 0u);
    }
};

QTEST_GUILESS_MAIN(TestTreeBuilder)
#include "tst_treebuilder.moc"
