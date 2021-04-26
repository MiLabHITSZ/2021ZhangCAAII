import tensorflow as tf


def test(model, test_db):
    total_correct_test = tf.constant(0, dtype=tf.int32)
    for (x, y) in test_db:
        out = model(x)
        out = tf.squeeze(out)
        pred = tf.argmax(out, axis=1)
        y = tf.argmax(y, axis=1)
        y = tf.cast(y, dtype=tf.int64)
        correct = tf.equal(pred, y)
        total_correct_test += tf.reduce_sum(tf.cast(correct, dtype=tf.int32))
    return total_correct_test / 10000


def cifar10_cnn_test(conv_net, fc_net, test_db, name):
    total_correct = tf.constant(0, dtype=tf.int32)
    for (x, y) in test_db:
        out1 = conv_net(x, training=True)
        pred = fc_net(out1, training=True)
        pred = tf.squeeze(pred, axis=[1, 2])
        pred = tf.argmax(pred, axis=1)
        y = tf.argmax(y, axis=1)
        # pred = tf.cast(pred, dtype=tf.int32)
        # y = tf.cast(y, dtype=tf.int64)
        correct = tf.equal(pred, y)
        total_correct += tf.reduce_sum(tf.cast(correct, dtype=tf.int32))
    if name == 'train_db':
        return total_correct / 50000
    elif name == "test_db":
        return total_correct / 10000
    elif name == "mal":
        return total_correct/2048

def mnist_cnn_test(model, test_db):
    total_correct_test = tf.constant(0, dtype=tf.int32)
    for (x, y) in test_db:
        out = model(x, training=True)
        out = tf.squeeze(out)
        pred = tf.argmax(out, axis=1)
        y = tf.argmax(y, axis=1)
        y = tf.cast(y, dtype=tf.int64)
        correct = tf.equal(pred, y)
        total_correct_test += tf.reduce_sum(tf.cast(correct, dtype=tf.int32))

    return total_correct_test / 10000
